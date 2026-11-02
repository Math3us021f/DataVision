"""Conta do próprio usuário: perfil, resumo de uso, acessos recentes, senha, sessões e e-mail de verificação."""

import logging

from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from ninja.errors import HttpError

from accounts.models import EmailCode, LoginEvent, User
from accounts.passwords import validate_new_password
from accounts.profile import avatar_color_of
from accounts.services import clean_email, ensure_email_free
from accounts.verification import (
    RESEND_COOLDOWN_SECONDS,
    CodeCooldownError,
    CodeRejectedError,
    TooManyCodesError,
    check_code,
    discard_code,
    email_change_message,
    issue_code,
    mask_email,
)
from audit.models import AuditLog
from audit.services import log_action
from core.mailer import MailNotConfiguredError, MailSendError, send_email
from core.rate_limit import is_locked_out, register_failed_attempt
from datasets.models import Dashboard, Dataset

logger = logging.getLogger("datavision")


def get_profile(user: User) -> dict:
    usage = Dataset.objects.filter(owner=user).aggregate(
        datasets=Count("id"), storage_bytes=Coalesce(Sum("size_bytes"), 0), profiled=Count("profile")
    )
    usage["dashboards"] = Dashboard.objects.filter(owner=user).count()
    return {
        "username": user.username,
        "is_admin": user.is_admin,
        "display_name": user.display_name,
        "avatar_color": avatar_color_of(user.preferences),
        "email_masked": mask_email(user.email),
        "member_since": user.created_at,
        "usage": usage,
    }


def update_profile(user: User, display_name: str | None, avatar_color: str | None) -> None:
    user.display_name = display_name
    user.preferences = {"avatar_color": avatar_color} if avatar_color else {}
    user.save(update_fields=["display_name", "preferences"])


def list_login_events(user: User, limit: int = 20) -> list[LoginEvent]:
    return list(LoginEvent.objects.filter(user=user).order_by("-id")[:limit])


def revoke_other_sessions(request) -> None:
    """Sobe a versão de sessão: todo cookie emitido antes deixa de valer. Esta sessão recebe a versão nova."""
    user = request.user
    with transaction.atomic():
        User.objects.filter(pk=user.pk).update(session_version=F("session_version") + 1)
        user.refresh_from_db(fields=["session_version"])
        log_action(user, AuditLog.Action.REVOKE_OTHER_SESSIONS, target=user)
    request.session["v"] = user.session_version
    logger.info("Outras sessões encerradas pelo próprio usuário: user_id=%s", user.pk)


def change_own_password(request, current_password: str, new_password: str) -> None:
    user = request.user
    # Exigir a senha atual impede que alguém com acesso a uma sessão aberta (ex.: computador destravado) troque a
    # senha e tome a conta.
    if not check_password(current_password, user.password):
        logger.warning("Troca de senha recusada (senha atual incorreta): user_id=%s", user.pk)
        raise HttpError(400, "Senha atual incorreta.")
    if new_password == current_password:
        raise HttpError(400, "A nova senha precisa ser diferente da atual.")
    validate_new_password(new_password)

    with transaction.atomic():
        user.set_password(new_password)
        user.session_version += 1  # as outras sessões ficam inválidas
        user.save(update_fields=["password", "session_version"])
        log_action(user, AuditLog.Action.CHANGE_OWN_PASSWORD, target=user)
    request.session["v"] = user.session_version  # esta sessão continua
    logger.info("Senha trocada pelo próprio usuário: user_id=%s", user.pk)


# ---------- E-mail de verificação (o da própria conta) ----------


def request_email_change(user: User, new_email_raw: str, current_password: str) -> dict:
    """Passo 1: pede a troca. A senha atual é exigida (uma sessão aberta e esquecida não pode redirecionar os códigos de
    login para outro endereço) e o código vai para o endereço NOVO, para provar que ele é da pessoa."""
    limit_key = ("alterar-email", user.username)
    if is_locked_out(limit_key):
        raise HttpError(429, "Muitas tentativas. Aguarde um minuto.")

    if not check_password(current_password, user.password):
        register_failed_attempt(limit_key)
        logger.warning("Troca de e-mail recusada (senha incorreta): user_id=%s", user.pk)
        raise HttpError(400, "Senha atual incorreta.")

    new_email = clean_email(new_email_raw)
    if new_email == (user.email or "").lower():
        raise HttpError(400, "Este já é o seu e-mail atual.")
    ensure_email_free(new_email, except_user_id=user.pk)

    try:
        code = issue_code(user, EmailCode.Purpose.EMAIL_CHANGE, new_email)
    except CodeCooldownError as exc:
        raise HttpError(429, f"Aguarde {exc.seconds_left} s para pedir outro código.")
    except TooManyCodesError:
        raise HttpError(429, "Muitos códigos pedidos. Tente mais tarde.")

    subject, body = email_change_message(code)
    try:
        send_email(new_email, subject, body)
    except (MailNotConfiguredError, MailSendError):
        discard_code(user, EmailCode.Purpose.EMAIL_CHANGE)
        raise HttpError(503, "Não foi possível enviar o código para esse endereço agora. Confira o e-mail e tente de novo.")
    logger.info("Código de troca de e-mail enviado: user_id=%s", user.pk)
    return {"email_hint": mask_email(new_email), "resend_in": RESEND_COOLDOWN_SECONDS}


def confirm_email_change(user: User, code: str) -> dict:
    """Passo 2: o código enviado ao endereço novo confirma a troca."""
    try:
        new_email = check_code(user, EmailCode.Purpose.EMAIL_CHANGE, code)
    except CodeRejectedError as exc:
        messages = {
            "wrong": f"Código incorreto. Você ainda tem {exc.attempts_left} tentativa(s).",
            "locked": "Muitas tentativas erradas. Peça um código novo.",
            "expired": "O código expirou. Peça um novo.",
            "missing": "Não há troca de e-mail pendente. Peça um código.",
        }
        raise HttpError(400, messages[exc.reason])

    with transaction.atomic():
        ensure_email_free(new_email, except_user_id=user.pk)  # pode ter sido usado por outra conta nesse meio-tempo
        before = mask_email(user.email) or "sem e-mail"
        user.email = new_email
        user.save(update_fields=["email"])
        log_action(user, AuditLog.Action.CHANGE_OWN_EMAIL, target=user, details=f"{before} → {mask_email(new_email)}")
    logger.info("E-mail alterado pelo próprio usuário: user_id=%s", user.pk)
    return {"email_masked": mask_email(new_email)}
