"""Peças do login compartilhadas entre a etapa da senha (POST /login) e a do código (POST /login/verify)."""

import logging

from django.conf import settings
from django.core import signing
from django.http import HttpRequest, HttpResponse, JsonResponse
from ninja.errors import HttpError

from accounts.events import record_login_event
from accounts.models import EmailCode, User
from accounts.session_policy import start_session
from accounts.verification import (
    CodeCooldownError,
    TooManyCodesError,
    discard_code,
    issue_code,
    login_code_message,
)
from core.mailer import MailNotConfiguredError, MailSendError, send_email
from core.rate_limit import reset_attempts

logger = logging.getLogger("datavision")

# Entre a senha e o código existe este cookie curto: prova que a senha foi aceita, mas NÃO é uma sessão
# (nenhuma rota o aceita no lugar dela). Vale 10 min, o mesmo prazo do código.
PENDING_COOKIE_NAME = "pending_login"
PENDING_MAX_AGE_SECONDS = 10 * 60
PENDING_SALT = "datavision-pending-login"

LOGIN_EXPIRED_DETAIL = "A verificação expirou. Entre novamente com usuário e senha."


def set_pending_cookie(response: HttpResponse, user: User) -> None:
    token = signing.dumps({"user_id": user.pk, "v": user.session_version}, salt=PENDING_SALT)
    response.set_cookie(
        PENDING_COOKIE_NAME,
        token,
        max_age=PENDING_MAX_AGE_SECONDS,
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )


def read_pending_login(token: str | None) -> User:
    """Devolve o usuário que passou pela senha e ainda precisa do código, ou levanta 401."""
    expired = HttpError(401, LOGIN_EXPIRED_DETAIL)
    if token is None:
        raise expired
    try:
        payload = signing.loads(token, salt=PENDING_SALT, max_age=PENDING_MAX_AGE_SECONDS)
    except signing.BadSignature:
        raise expired

    user = User.objects.filter(pk=payload["user_id"]).first()
    # Conta desativada ou senha trocada no meio do caminho: recomeça.
    if user is None or not user.is_active or user.session_version != payload["v"]:
        raise expired
    return user


def client_ip(request: HttpRequest) -> str:
    return request.META.get("REMOTE_ADDR") or "desconhecido"


def rate_limit_key(request: HttpRequest, username: str) -> tuple[str, str]:
    return (client_ip(request), username)


def record_login(user: User, success: bool, request: HttpRequest) -> None:
    record_login_event(user, success, request.headers.get("user-agent"))


def complete_login(request: HttpRequest, user: User) -> HttpResponse:
    """Passou por tudo (senha e, se houver, código): registra o acesso e entrega a sessão."""
    reset_attempts(rate_limit_key(request, user.username))
    record_login(user, True, request)
    logger.info("Login bem-sucedido: user_id=%s username=%r", user.pk, user.username)
    start_session(request, user)
    response = JsonResponse({"status": "ok"})
    response.delete_cookie(PENDING_COOKIE_NAME)
    return response


def send_login_code(user: User) -> bool:
    """Gera e envia o código de login. Devolve False se já havia um enviado há pouco (ele continua valendo).
    Se o e-mail não puder ser enviado, o código é descartado e a resposta é 503: o login fica bloqueado
    até o e-mail funcionar (ou um administrador resolver). Preferimos isso a um modo de "pular o código"."""
    try:
        code = issue_code(user, EmailCode.Purpose.LOGIN)
    except CodeCooldownError:
        return False
    except TooManyCodesError:
        raise HttpError(429, "Muitos códigos pedidos. Aguarde um pouco antes de tentar de novo.")

    subject, body = login_code_message(code)
    try:
        send_email(user.email, subject, body)
    except (MailNotConfiguredError, MailSendError):
        discard_code(user, EmailCode.Purpose.LOGIN)
        logger.error("Código de login não enviado: user_id=%s", user.pk)
        raise HttpError(
            503,
            "Não foi possível enviar o código por e-mail agora. Tente de novo em instantes ou peça ajuda a um administrador.",
        )
    logger.info("Código de login enviado: user_id=%s", user.pk)
    return True
