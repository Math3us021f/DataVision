import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.auth import (
    SESSION_COOKIE_NAME,
    burn_password_check,
    create_session_token,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from src.core.db import get_connection
from src.core.logging_config import logger, setup_logging
from src.core.rate_limit import is_locked_out, register_failed_attempt, reset_attempts
from src.routers.api.account import router as account_router
from src.routers.api.analytics import router as analytics_router
from src.routers.api.audit import router as audit_router
from src.routers.api.dashboard import router as dashboard_router
from src.routers.api.datasets import router as datasets_router
from src.routers.api.files import router as files_router
from src.routers.api.logs import router as logs_router
from src.routers.api.metrics import router as metrics_router
from src.routers.api.users import router as users_router
from src.routers.web.web import router as web_router
from src.core.storage import ensure_bucket
from src.services.account import avatar_color_of, record_login_event


def init_db() -> None:
    """Cria/atualiza as tabelas e garante um admin inicial."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
        )
        conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                actor_user_id INTEGER NOT NULL REFERENCES users (id),
                action TEXT NOT NULL,
                target_user_id INTEGER REFERENCES users (id),
                details TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Excluir um usuário não pode apagar nem travar o histórico de auditoria:
        # as referências passam a ficar vazias (NULL) e o registro permanece.
        conn.execute("ALTER TABLE audit_logs ALTER COLUMN actor_user_id DROP NOT NULL")
        for column in ("actor_user_id", "target_user_id"):
            constraint = f"audit_logs_{column}_fkey"
            conn.execute(f"ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS {constraint}")
            conn.execute(
                f"ALTER TABLE audit_logs ADD CONSTRAINT {constraint} "
                f"FOREIGN KEY ({column}) REFERENCES users (id) ON DELETE SET NULL"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id SERIAL PRIMARY KEY,
                owner_user_id INTEGER NOT NULL REFERENCES users (id),
                original_name TEXT NOT NULL,
                object_key TEXT UNIQUE NOT NULL,
                format TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_profiles (
                id SERIAL PRIMARY KEY,
                dataset_id INTEGER UNIQUE NOT NULL REFERENCES datasets (id),
                row_count INTEGER NOT NULL,
                duplicate_row_count INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_columns (
                id SERIAL PRIMARY KEY,
                dataset_id INTEGER NOT NULL REFERENCES datasets (id),
                column_name TEXT NOT NULL,
                inferred_type TEXT NOT NULL,
                null_count INTEGER NOT NULL,
                distinct_count INTEGER NOT NULL,
                min_value DOUBLE PRECISION,
                max_value DOUBLE PRECISION,
                mean_value DOUBLE PRECISION,
                median_value DOUBLE PRECISION,
                histogram JSONB
            )
            """
        )
        for column in ("min_value", "max_value", "mean_value", "median_value"):
            conn.execute(f"ALTER TABLE dataset_columns ADD COLUMN IF NOT EXISTS {column} DOUBLE PRECISION")
        conn.execute("ALTER TABLE dataset_columns ADD COLUMN IF NOT EXISTS histogram JSONB")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_column_top_values (
                id SERIAL PRIMARY KEY,
                dataset_column_id INTEGER NOT NULL REFERENCES dataset_columns (id) ON DELETE CASCADE,
                value TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL
            )
            """
        )
        # Um dashboard salvo por dataset (UNIQUE). ON DELETE CASCADE: apagar o dataset (ou o usuário,
        # que apaga os datasets antes) leva o dashboard junto, sem DELETE manual extra.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboards (
                id SERIAL PRIMARY KEY,
                dataset_id INTEGER NOT NULL UNIQUE REFERENCES datasets (id) ON DELETE CASCADE,
                owner_user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                spec JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Perfil do próprio usuário: nome de exibição opcional e preferências (JSONB validado no servidor).
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb")
        # Acessos recentes de cada usuário. De propósito NÃO guarda IP nem o texto do navegador:
        # só data, resultado e um resumo ("Chrome · Windows"). ON DELETE CASCADE com o usuário.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                success BOOLEAN NOT NULL,
                browser TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS login_events_user_idx ON login_events (user_id, id DESC)")
        row = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        if row["total"] == 0:
            admin_username = os.environ["ADMIN_USERNAME"]
            admin_password = os.environ["ADMIN_PASSWORD"]
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, TRUE)",
                (admin_username, hash_password(admin_password)),
            )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    ensure_bucket()
    logger.info("Aplicação iniciada")
    yield


# Em produção (APP_ENV=production) a documentação interativa some: /docs e /openapi.json são
# públicos (sem login) e listariam todas as rotas, inclusive as administrativas.
_docs_enabled = os.environ.get("APP_ENV", "development") != "production"

app = FastAPI(
    title="DataVision",
    description="API para análise automática de arquivos de dados.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")  # impede a aplicação de ser embutida em outro site (clickjacking)
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response

app.include_router(users_router)
app.include_router(metrics_router)
app.include_router(logs_router)
app.include_router(files_router)
app.include_router(datasets_router)
app.include_router(account_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(dashboard_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "application": "DataVision",
    }


def _record_login(user_id: int, success: bool, request: Request) -> None:
    with get_connection() as conn:
        record_login_event(conn, user_id, success, request.headers.get("user-agent"))
        conn.commit()


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(credentials: LoginRequest, request: Request, response: Response) -> dict[str, str]:
    rate_limit_key = (request.client.host if request.client else "desconhecido", credentials.username)

    if is_locked_out(rate_limit_key):
        logger.warning("Login bloqueado por excesso de tentativas: username=%r", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Aguarde um minuto e tente novamente.",
        )

    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, password_hash, is_active, session_version FROM users WHERE username = %s",
            (credentials.username,),
        ).fetchone()

    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha inválidos"
    )

    if user is None:
        burn_password_check(credentials.password)
        password_ok = False
    else:
        password_ok = verify_password(credentials.password, user["password_hash"])

    if not password_ok:
        if user is not None:
            _record_login(user["id"], False, request)
        register_failed_attempt(rate_limit_key)
        logger.warning("Login falhou para username=%r", credentials.username)
        raise credenciais_invalidas

    if not user["is_active"]:
        # Mesma mensagem genérica do caso de senha errada: não revelamos que a conta existe, mas está desativada.
        _record_login(user["id"], False, request)
        register_failed_attempt(rate_limit_key)
        logger.warning("Login negado (conta inativa) para username=%r", credentials.username)
        raise credenciais_invalidas

    reset_attempts(rate_limit_key)
    _record_login(user["id"], True, request)
    logger.info("Login bem-sucedido: user_id=%s username=%r", user["id"], credentials.username)
    token = create_session_token(user["id"], user["session_version"])
    set_session_cookie(response, token)
    return {"status": "ok"}


@app.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"status": "ok"}


@app.get("/me")
def me(current_user: dict = Depends(get_current_user)) -> dict:
    return {
        "username": current_user["username"],
        "is_admin": current_user["is_admin"],
        "display_name": current_user["display_name"],
        "avatar_color": avatar_color_of(current_user["preferences"]),
    }
