"""Peças do login compartilhadas entre a etapa da senha (POST /login) e a do código (POST /login/verify)."""

import os

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from src.core.auth import create_session_token, set_session_cookie
from src.core.db import get_connection
from src.core.logging_config import logger
from src.core.rate_limit import reset_attempts
from src.services.account import record_login_event

# Entre a senha e o código existe este cookie curto: prova que a senha foi aceita, mas NÃO é uma sessão
# (nenhuma rota o aceita no lugar dela). Vale 10 min, o mesmo prazo do código.
PENDING_COOKIE_NAME = "pending_login"
PENDING_MAX_AGE_SECONDS = 10 * 60

LOGIN_EXPIRED_DETAIL = "A verificação expirou. Entre novamente com usuário e senha."


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(os.environ["SECRET_KEY"], salt="datavision-pending-login")


def _secure_cookie() -> bool:
    return os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"


def set_pending_cookie(response: Response, user_id: int, session_version: int) -> None:
    response.set_cookie(
        key=PENDING_COOKIE_NAME,
        value=_serializer().dumps({"user_id": user_id, "v": session_version}),
        max_age=PENDING_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(),
    )


def clear_pending_cookie(response: Response) -> None:
    response.delete_cookie(key=PENDING_COOKIE_NAME)


def read_pending_login(token: str | None) -> dict:
    """Devolve o usuário (do banco) que passou pela senha e ainda precisa do código, ou levanta 401."""
    expired = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_EXPIRED_DETAIL)
    if token is None:
        raise expired
    try:
        payload = _serializer().loads(token, max_age=PENDING_MAX_AGE_SECONDS)
    except BadSignature:
        raise expired

    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, username, email, is_active, session_version FROM users WHERE id = %s", (payload["user_id"],)
        ).fetchone()
    # Conta desativada ou senha trocada no meio do caminho: recomeça.
    if user is None or not user["is_active"] or user["session_version"] != payload["v"]:
        raise expired
    return user


def rate_limit_key(request: Request, username: str) -> tuple[str, str]:
    return (request.client.host if request.client else "desconhecido", username)


def record_login(user_id: int, success: bool, request: Request) -> None:
    with get_connection() as conn:
        record_login_event(conn, user_id, success, request.headers.get("user-agent"))
        conn.commit()


def complete_login(response: Response, request: Request, user: dict) -> None:
    """Passou por tudo (senha e, se houver, código): registra o acesso e entrega a sessão."""
    reset_attempts(rate_limit_key(request, user["username"]))
    record_login(user["id"], True, request)
    logger.info("Login bem-sucedido: user_id=%s username=%r", user["id"], user["username"])
    set_session_cookie(response, create_session_token(user["id"], user["session_version"]))
    clear_pending_cookie(response)
