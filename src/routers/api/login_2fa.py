"""Segunda etapa do login: o código enviado por e-mail. A primeira etapa (usuário e senha) é POST /login."""

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.core.db import get_connection
from src.core.logging_config import logger
from src.core.login_flow import PENDING_COOKIE_NAME, complete_login, read_pending_login, record_login
from src.core.mailer import MailNotConfiguredError, MailSendError, send_email
from src.services.verification import (
    RESEND_COOLDOWN_SECONDS,
    CodeCooldownError,
    CodeRejectedError,
    TooManyCodesError,
    check_code,
    discard_code,
    issue_code,
    login_code_message,
)

router = APIRouter(tags=["auth"])


def send_login_code(user: dict) -> bool:
    """Gera e envia o código de login. Devolve False se já havia um enviado há pouco (ele continua valendo).
    Se o e-mail não puder ser enviado, o código é descartado e a resposta é 503: o login fica bloqueado
    até o e-mail funcionar (ou um administrador resolver). Preferimos isso a um modo de "pular o código"."""
    with get_connection() as conn:
        try:
            code = issue_code(conn, user["id"], "login")
        except CodeCooldownError:
            conn.rollback()
            return False
        except TooManyCodesError:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitos códigos pedidos. Aguarde um pouco antes de tentar de novo.",
            )
        conn.commit()

    subject, body = login_code_message(code)
    try:
        send_email(user["email"], subject, body)
    except (MailNotConfiguredError, MailSendError):
        with get_connection() as conn:
            discard_code(conn, user["id"], "login")
            conn.commit()
        logger.error("Código de login não enviado: user_id=%s", user["id"])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enviar o código por e-mail agora. Tente de novo em instantes ou peça ajuda a um administrador.",
        )
    logger.info("Código de login enviado: user_id=%s", user["id"])
    return True


class VerifyRequest(BaseModel):
    code: str = Field(max_length=32)


@router.post("/login/verify")
def verify_login(
    data: VerifyRequest,
    request: Request,
    response: Response,
    pending_login: str | None = Cookie(default=None, alias=PENDING_COOKIE_NAME),
) -> dict[str, str]:
    user = read_pending_login(pending_login)

    with get_connection() as conn:
        try:
            check_code(conn, user["id"], "login", data.code)
            conn.commit()
        except CodeRejectedError as exc:
            conn.commit()  # guarda a tentativa contada (ou o código descartado)
            if exc.reason == "wrong":
                logger.warning("Código de login incorreto: user_id=%s", user["id"])
                plural = "tentativa" if exc.attempts_left == 1 else "tentativas"
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Código incorreto. Você ainda tem {exc.attempts_left} {plural}.",
                )
            if exc.reason == "locked":
                record_login(user["id"], False, request)  # entra no histórico de acessos da conta
                logger.warning("Código de login esgotado por tentativas erradas: user_id=%s", user["id"])
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Muitas tentativas erradas. Entre novamente com usuário e senha para receber um código novo.",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="O código expirou. Entre novamente com usuário e senha para receber um novo.",
            )

    complete_login(response, request, user)
    return {"status": "ok"}


@router.post("/login/resend")
def resend_login_code(
    pending_login: str | None = Cookie(default=None, alias=PENDING_COOKIE_NAME),
) -> dict[str, int]:
    user = read_pending_login(pending_login)
    if not send_login_code(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Aguarde um pouco antes de pedir outro código (cerca de {RESEND_COOLDOWN_SECONDS} s entre pedidos).",
        )
    return {"resend_in": RESEND_COOLDOWN_SECONDS}
