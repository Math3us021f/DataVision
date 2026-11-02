"""Rotas de autenticação: login (em duas etapas, se a conta tem e-mail), logout e quem sou eu."""

import logging

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from accounts.auth import CsrfProtected, SessionAuth
from accounts.login_flow import (
    PENDING_COOKIE_NAME,
    complete_login,
    rate_limit_key,
    read_pending_login,
    record_login,
    send_login_code,
    set_pending_cookie,
)
from accounts.models import EmailCode, User
from accounts.profile import avatar_color_of
from accounts.verification import (
    RESEND_COOLDOWN_SECONDS,
    CodeRejectedError,
    check_code,
    mask_email,
)
from core import views
from core.rate_limit import is_locked_out, register_failed_attempt

logger = logging.getLogger("datavision")
router = Router(tags=["autenticação"])

# Um hash qualquer para gastar o mesmo tempo quando o usuário não existe: sem isso, login de usuário inexistente
# responde bem mais rápido que senha errada de usuário existente, e a diferença de tempo revela quais contas existem.
_DUMMY_PASSWORD_HASH = make_password("senha-descartavel-so-para-gastar-tempo")
# Senha enorme não é verificada (seria só custo de CPU para um atacante): conta como senha errada, como no FastAPI.
MAX_LOGIN_PASSWORD_BYTES = 1024


class LoginIn(Schema):
    username: str
    password: str


class CodeIn(Schema):
    code: str = Field(max_length=32)


class MeOut(Schema):
    username: str
    is_admin: bool
    display_name: str | None
    avatar_color: str | None
    email_masked: str | None
    idle_timeout_seconds: int


def _password_matches(user: User | None, password: str) -> bool:
    if len(password.encode("utf-8")) > MAX_LOGIN_PASSWORD_BYTES:
        check_password("x", _DUMMY_PASSWORD_HASH)  # mesmo custo de uma verificação normal
        return False
    if user is None:
        check_password(password, _DUMMY_PASSWORD_HASH)
        return False
    return check_password(password, user.password)


@router.post("/login", auth=CsrfProtected(), summary="Primeira etapa do login (usuário e senha)")
def login(request, data: LoginIn):
    """Quem não tem e-mail cadastrado entra só com a senha; quem tem recebe um código por e-mail e conclui em
    `POST /login/verify` (ainda sem sessão até lá)."""
    key = rate_limit_key(request, data.username)
    if is_locked_out(key):
        logger.warning("Login bloqueado por excesso de tentativas: username=%r", data.username)
        raise HttpError(429, "Muitas tentativas de login. Aguarde um minuto e tente novamente.")

    user = User.objects.filter(username=data.username).first()
    invalid = HttpError(401, "Usuário ou senha inválidos")

    if not _password_matches(user, data.password):
        if user is not None:
            record_login(user, False, request)
        register_failed_attempt(key)
        logger.warning("Login falhou para username=%r", data.username)
        raise invalid

    if not user.is_active:
        # Mesma mensagem genérica do caso de senha errada: não revelamos que a conta existe, mas está desativada.
        record_login(user, False, request)
        register_failed_attempt(key)
        logger.warning("Login negado (conta inativa) para username=%r", data.username)
        raise invalid

    if user.email:
        # Senha certa, mas ainda não há sessão: falta o código enviado ao e-mail da conta.
        sent_now = send_login_code(user)
        response = JsonResponse(
            {"status": "2fa_required", "email_hint": mask_email(user.email), "resend_in": RESEND_COOLDOWN_SECONDS if sent_now else 0}
        )
        set_pending_cookie(response, user)
        return response

    return complete_login(request, user)


@router.post("/login/verify", auth=CsrfProtected(), summary="Segunda etapa do login (código do e-mail)")
def verify_login(request, data: CodeIn):
    user = read_pending_login(request.COOKIES.get(PENDING_COOKIE_NAME))

    try:
        check_code(user, EmailCode.Purpose.LOGIN, data.code)
    except CodeRejectedError as exc:
        if exc.reason == "wrong":
            logger.warning("Código de login incorreto: user_id=%s", user.pk)
            plural = "tentativa" if exc.attempts_left == 1 else "tentativas"
            raise HttpError(401, f"Código incorreto. Você ainda tem {exc.attempts_left} {plural}.")
        if exc.reason == "locked":
            record_login(user, False, request)  # entra no histórico de acessos da conta
            logger.warning("Código de login esgotado por tentativas erradas: user_id=%s", user.pk)
            raise HttpError(401, "Muitas tentativas erradas. Entre novamente com usuário e senha para receber um código novo.")
        raise HttpError(401, "O código expirou. Entre novamente com usuário e senha para receber um novo.")

    return complete_login(request, user)


@router.post("/login/resend", auth=CsrfProtected(), summary="Reenvia o código de login")
def resend_login_code(request):
    user = read_pending_login(request.COOKIES.get(PENDING_COOKIE_NAME))
    if not send_login_code(user):
        raise HttpError(429, f"Aguarde um pouco antes de pedir outro código (cerca de {RESEND_COOLDOWN_SECONDS} s entre pedidos).")
    return {"resend_in": RESEND_COOLDOWN_SECONDS}


@router.post("/logout", auth=CsrfProtected(), summary="Encerra a sessão")
def logout_view(request):
    logout(request)  # apaga a sessão no banco e o cookie
    return {"status": "ok"}


@router.get("/me", auth=SessionAuth(), response=MeOut, summary="Quem sou eu")
def me(request):
    user = request.auth
    return {
        "username": user.username,
        "is_admin": user.is_admin,
        "display_name": user.display_name,
        "avatar_color": avatar_color_of(user.preferences),
        # Sempre mascarado; null = sem e-mail cadastrado (a interface lembra a pessoa de cadastrar um).
        "email_masked": mask_email(user.email),
        # O navegador usa este valor para avisar antes de a sessão cair; quem encerra de verdade é o servidor.
        "idle_timeout_seconds": settings.SESSION_IDLE_TIMEOUT_SECONDS,
    }


@router.get("/login", auth=None, include_in_schema=False)
def login_page(request):
    """A tela de entrada (o React), na mesma URL do POST /login: o Ninja só junta métodos de uma URL dentro do
    mesmo roteador. Fica fora da documentação: é uma página, não parte da API."""
    return views.login_page(request)
