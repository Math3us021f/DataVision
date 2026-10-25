import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    get_current_user,
    hash_password,
    verify_password,
)
from src.db import get_connection
from src.logging_config import logger, setup_logging
from src.rate_limit import is_locked_out, register_failed_attempt, reset_attempts
from src.routers.account import router as account_router
from src.routers.datasets import router as datasets_router
from src.routers.files import router as files_router
from src.routers.logs import router as logs_router
from src.routers.metrics import router as metrics_router
from src.routers.users import router as users_router
from src.routers.web import router as web_router
from src.storage import ensure_bucket


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
                distinct_count INTEGER NOT NULL
            )
            """
        )
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


app = FastAPI(
    title="DataVision",
    description="API para análise automática de arquivos de dados.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(users_router)
app.include_router(metrics_router)
app.include_router(logs_router)
app.include_router(files_router)
app.include_router(datasets_router)
app.include_router(account_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "application": "DataVision",
    }


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

    if user is None or not verify_password(credentials.password, user["password_hash"]):
        register_failed_attempt(rate_limit_key)
        logger.warning("Login falhou para username=%r", credentials.username)
        raise credenciais_invalidas

    if not user["is_active"]:
        # Mesma mensagem genérica do caso de senha errada: não revelamos que a conta existe, mas está desativada.
        register_failed_attempt(rate_limit_key)
        logger.warning("Login negado (conta inativa) para username=%r", credentials.username)
        raise credenciais_invalidas

    reset_attempts(rate_limit_key)
    logger.info("Login bem-sucedido: user_id=%s username=%r", user["id"], credentials.username)
    token = create_session_token(user["id"], user["session_version"])
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
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
    }
