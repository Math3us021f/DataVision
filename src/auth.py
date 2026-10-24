import os

import bcrypt
from fastapi import Cookie, Depends, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.db import get_connection

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 8  # 8 horas


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _get_serializer() -> URLSafeTimedSerializer:
    secret_key = os.environ["SECRET_KEY"]
    return URLSafeTimedSerializer(secret_key, salt="datavision-session")


def create_session_token(user_id: int) -> str:
    """O cookie guarda só o id do usuário; permissões são sempre lidas do banco, nunca do cookie."""
    serializer = _get_serializer()
    return serializer.dumps({"user_id": user_id})


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
            "SELECT id, username, is_admin, is_active FROM users WHERE id = %s",
            (payload["user_id"],),
        ).fetchone()

    if user is None or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency do FastAPI: exige sessão válida E que o usuário seja administrador."""
    if not current_user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requer privilégio de administrador")
    return current_user
