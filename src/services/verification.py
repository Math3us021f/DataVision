"""Códigos de verificação por e-mail (login em dois passos e confirmação de troca de e-mail).

O código nunca é guardado: só um HMAC dele (chave = SECRET_KEY), amarrado ao usuário e à finalidade.
Vale 10 minutos, aceita poucas tentativas, é de uso único e só pode ser reenviado depois de uma pausa.
"""

import hashlib
import hmac
import os
import re
import secrets
from typing import Literal

CODE_DIGITS = 6
CODE_VALID_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30
MAX_SENDS_PER_HOUR = 10
MAX_EMAIL_LENGTH = 254

Purpose = Literal["login", "email_change"]

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
    key = os.environ["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, f"{purpose}:{user_id}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def issue_code(conn, user_id: int, purpose: Purpose, new_email: str | None = None) -> str:
    """Cria (ou substitui) o código pendente do usuário para esta finalidade e devolve o código em texto,
    só para quem vai enviá-lo. Levanta CodeCooldownError / TooManyCodesError se for cedo demais ou demais."""
    row = conn.execute(
        """
        SELECT EXTRACT(EPOCH FROM (now() - last_sent_at)) AS since_last,
               EXTRACT(EPOCH FROM (now() - window_started_at)) AS window_age,
               sends_in_window
        FROM email_codes WHERE user_id = %s AND purpose = %s FOR UPDATE
        """,
        (user_id, purpose),
    ).fetchone()

    sends = 1
    window_reset = True
    if row is not None:
        if row["since_last"] < RESEND_COOLDOWN_SECONDS:
            raise CodeCooldownError(int(RESEND_COOLDOWN_SECONDS - row["since_last"]) + 1)
        if row["window_age"] < 3600:
            if row["sends_in_window"] >= MAX_SENDS_PER_HOUR:
                raise TooManyCodesError
            sends = row["sends_in_window"] + 1
            window_reset = False

    code = _generate_code()
    conn.execute(
        f"""
        INSERT INTO email_codes (user_id, purpose, code_hash, new_email, expires_at, attempts, last_sent_at,
                                 window_started_at, sends_in_window)
        VALUES (%s, %s, %s, %s, now() + make_interval(mins => %s), 0, now(), now(), %s)
        ON CONFLICT (user_id, purpose) DO UPDATE SET
            code_hash = EXCLUDED.code_hash, new_email = EXCLUDED.new_email, expires_at = EXCLUDED.expires_at,
            attempts = 0, last_sent_at = now(), sends_in_window = EXCLUDED.sends_in_window
            {', window_started_at = now()' if window_reset else ''}
        """,
        (user_id, purpose, _hash_code(user_id, purpose, code), new_email, CODE_VALID_MINUTES, sends),
    )
    return code


def discard_code(conn, user_id: int, purpose: Purpose) -> None:
    conn.execute("DELETE FROM email_codes WHERE user_id = %s AND purpose = %s", (user_id, purpose))


def check_code(conn, user_id: int, purpose: Purpose, code: str) -> str | None:
    """Confere o código. Se estiver certo, ele é consumido e a função devolve o `new_email` guardado
    (ou None). Se não, levanta CodeRejectedError — e conta a tentativa, esgotando o código na 5ª."""
    row = conn.execute(
        """
        SELECT code_hash, new_email, attempts, expires_at <= now() AS expired
        FROM email_codes WHERE user_id = %s AND purpose = %s FOR UPDATE
        """,
        (user_id, purpose),
    ).fetchone()
    if row is None:
        raise CodeRejectedError("missing")
    if row["expired"]:
        discard_code(conn, user_id, purpose)
        raise CodeRejectedError("expired")
    if row["attempts"] >= MAX_ATTEMPTS:
        discard_code(conn, user_id, purpose)
        raise CodeRejectedError("locked")

    clean = re.sub(r"\s+", "", code)
    if clean.isdigit() and len(clean) == CODE_DIGITS and hmac.compare_digest(_hash_code(user_id, purpose, clean), row["code_hash"]):
        discard_code(conn, user_id, purpose)
        return row["new_email"]

    attempts = row["attempts"] + 1
    if attempts >= MAX_ATTEMPTS:
        discard_code(conn, user_id, purpose)
        raise CodeRejectedError("locked")
    conn.execute("UPDATE email_codes SET attempts = %s WHERE user_id = %s AND purpose = %s", (attempts, user_id, purpose))
    raise CodeRejectedError("wrong", attempts_left=MAX_ATTEMPTS - attempts)


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
