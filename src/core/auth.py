import os

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.core.db import get_connection

MIN_PASSWORD_LENGTH = 8

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 8  # 8 horas


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


MAX_PASSWORD_BYTES = 72  # limite do bcrypt


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        # Nenhuma senha cadastrada passa de 72 bytes (validate_new_password); e versões novas do
        # bcrypt levantam ValueError nesse caso, o que viraria um erro 500 no login.
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


_DUMMY_PASSWORD_HASH = hash_password("senha-descartavel-so-para-gastar-tempo")


def burn_password_check(password: str) -> None:
    """Gasta o mesmo tempo de uma verificação real. Sem isso, login de usuário inexistente responde
    bem mais rápido que senha errada de usuário existente, e a diferença de tempo revela quais contas existem."""
    verify_password(password, _DUMMY_PASSWORD_HASH)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        # Em produção com HTTPS, ligar SESSION_COOKIE_SECURE=true. Lido a cada chamada, não no import.
        secure=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
    )


def validate_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.",
        )
    # bcrypt só considera os primeiros 72 bytes; acima disso o resto seria ignorado em silêncio.
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha pode ter no máximo 72 bytes.",
        )


def _get_serializer() -> URLSafeTimedSerializer:
    secret_key = os.environ["SECRET_KEY"]
    return URLSafeTimedSerializer(secret_key, salt="datavision-session")


def create_session_token(user_id: int, session_version: int) -> str:
    """O cookie guarda só o id e a versão de sessão; permissões são sempre lidas do banco.
    Trocar a senha incrementa session_version no banco, invalidando cookies emitidos antes."""
    serializer = _get_serializer()
    return serializer.dumps({"user_id": user_id, "v": session_version})


def _read_session_token(token: str) -> dict:
    serializer = _get_serializer()
    try:
        return serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")


def get_current_user(session: str | None = Cookie(default=None)) -> dict:
    """Dependency do FastAPI: exige sessão válida e usuário ativo, com dados sempre atuais do banco."""
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    payload = _read_session_token(session)

    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, username, is_admin, is_active, session_version FROM users WHERE id = %s",
            (payload["user_id"],),
        ).fetchone()

    if user is None or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    # Cookies emitidos antes da última troca de senha deixam de valer.
    if payload.get("v") != user["session_version"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão encerrada")

    return user


def get_current_user_optional(session: str | None = Cookie(default=None)) -> dict | None:
    """Como get_current_user, mas devolve None em vez de 401 — para páginas que decidem
    o que mostrar (ex: redirecionar pro login) em vez de simplesmente barrar o acesso."""
    if session is None:
        return None
    try:
        return get_current_user(session)
    except HTTPException:
        return None


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency do FastAPI: exige sessão válida E que o usuário seja administrador."""
    if not current_user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requer privilégio de administrador")
    return current_user
