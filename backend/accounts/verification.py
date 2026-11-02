"""Códigos de verificação por e-mail (login em dois passos e confirmação de troca de e-mail).

O código nunca é guardado: só um HMAC dele (chave = SECRET_KEY), amarrado ao usuário e à finalidade.
Vale 10 minutos, aceita poucas tentativas, é de uso único e só pode ser reenviado depois de uma pausa.
"""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from typing import Literal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import EmailCode

CODE_DIGITS = 6
CODE_VALID_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30
MAX_SENDS_PER_HOUR = 10
MAX_EMAIL_LENGTH = 254

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvalidEmailError(ValueError):
    pass


class CodeCooldownError(Exception):
    def __init__(self, seconds_left: int) -> None:
        super().__init__(seconds_left)
        self.seconds_left = seconds_left


class TooManyCodesError(Exception):
    """Muitos códigos pedidos na última hora."""


class CodeRejectedError(Exception):
    """Código errado, vencido ou com tentativas esgotadas. `reason` orienta a mensagem; `attempts_left` só vale para 'wrong'."""

    def __init__(self, reason: Literal["wrong", "expired", "locked", "missing"], attempts_left: int = 0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.attempts_left = attempts_left


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if not email or len(email) > MAX_EMAIL_LENGTH or not _EMAIL_PATTERN.match(email) or any(ord(c) < 32 for c in email):
        raise InvalidEmailError("Informe um e-mail válido.")
    return email


def mask_email(email: str | None) -> str | None:
    """`maria@gmail.com` → `m***@gmail.com`. É assim que o e-mail aparece em toda a interface."""
    if not email:
        return None
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _hash_code(user_id: int, purpose: str, code: str) -> str:
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, f"{purpose}:{user_id}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def issue_code(user, purpose: str, new_email: str | None = None) -> str:
    """Cria (ou substitui) o código pendente do usuário para esta finalidade e devolve o código em texto,
    só para quem vai enviá-lo. Levanta CodeCooldownError / TooManyCodesError se for cedo demais ou demais."""
    with transaction.atomic():
        # select_for_update trava a linha: dois pedidos ao mesmo tempo não furam a pausa nem o teto por hora.
        row = EmailCode.objects.select_for_update().filter(user=user, purpose=purpose).first()
        now = timezone.now()
        sends, window_start = 1, now
        if row is not None:
            since_last = (now - row.last_sent_at).total_seconds()
            if since_last < RESEND_COOLDOWN_SECONDS:
                raise CodeCooldownError(int(RESEND_COOLDOWN_SECONDS - since_last) + 1)
            if (now - row.window_started_at).total_seconds() < 3600:
                if row.sends_in_window >= MAX_SENDS_PER_HOUR:
                    raise TooManyCodesError
                sends, window_start = row.sends_in_window + 1, row.window_started_at

        code = _generate_code()
        EmailCode.objects.update_or_create(
            user=user,
            purpose=purpose,
            defaults={
                "code_hash": _hash_code(user.pk, purpose, code),
                "new_email": new_email,
                "expires_at": now + timedelta(minutes=CODE_VALID_MINUTES),
                "attempts": 0,
                "last_sent_at": now,
                "window_started_at": window_start,
                "sends_in_window": sends,
            },
        )
        return code


def discard_code(user, purpose: str) -> None:
    EmailCode.objects.filter(user=user, purpose=purpose).delete()


def check_code(user, purpose: str, code: str) -> str | None:
    """Confere o código. Se estiver certo, ele é consumido e a função devolve o `new_email` guardado
    (ou None). Se não, levanta CodeRejectedError — e a tentativa errada FICA contada (5ª esgota o código).

    O resultado é calculado dentro da transação e a exceção só é levantada DEPOIS dela: uma exceção dentro
    do `atomic()` desfaria o contador de tentativas, e o código poderia ser adivinhado sem limite."""
    rejection: CodeRejectedError | None = None
    new_email: str | None = None

    with transaction.atomic():
        row = EmailCode.objects.select_for_update().filter(user=user, purpose=purpose).first()
        if row is None:
            rejection = CodeRejectedError("missing")
        elif row.expires_at <= timezone.now():
            row.delete()
            rejection = CodeRejectedError("expired")
        elif row.attempts >= MAX_ATTEMPTS:
            row.delete()
            rejection = CodeRejectedError("locked")
        else:
            clean = re.sub(r"\s+", "", code)
            if clean.isdigit() and len(clean) == CODE_DIGITS and hmac.compare_digest(_hash_code(user.pk, purpose, clean), row.code_hash):
                new_email = row.new_email
                row.delete()  # uso único
            else:
                row.attempts += 1
                if row.attempts >= MAX_ATTEMPTS:
                    row.delete()
                    rejection = CodeRejectedError("locked")
                else:
                    row.save(update_fields=["attempts"])
                    rejection = CodeRejectedError("wrong", attempts_left=MAX_ATTEMPTS - row.attempts)

    if rejection is not None:
        raise rejection
    return new_email


def login_code_message(code: str) -> tuple[str, str]:
    return (
        "Seu código de acesso ao DataVision",
        f"Seu código de acesso é: {code}\n\n"
        f"Ele vale por {CODE_VALID_MINUTES} minutos e só pode ser usado uma vez.\n"
        "Se não foi você que tentou entrar, ignore esta mensagem e troque a sua senha em \"Minha conta\".\n",
    )


def email_change_message(code: str) -> tuple[str, str]:
    return (
        "Confirme seu e-mail no DataVision",
        f"Seu código para confirmar este e-mail é: {code}\n\n"
        f"Ele vale por {CODE_VALID_MINUTES} minutos e só pode ser usado uma vez.\n"
        "Se você não pediu isso, ignore esta mensagem: nada será alterado.\n",
    )
