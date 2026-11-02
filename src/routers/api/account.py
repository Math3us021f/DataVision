from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.auth import (
    create_session_token,
    get_current_user,
    hash_password,
    set_session_cookie,
    validate_new_password,
    verify_password,
)
from src.core.db import get_connection
from src.core.logging_config import logger
from src.core.mailer import MailNotConfiguredError, MailSendError, send_email
from src.core.rate_limit import is_locked_out, register_failed_attempt
from src.services.account import (
    AVATAR_COLORS,
    MAX_DISPLAY_NAME,
    get_profile,
    list_login_events,
    revoke_other_sessions,
    update_profile,
)
from src.services.notifications import list_notifications, mark_all_read
from src.services.users import clean_email, ensure_email_free
from src.services.verification import (
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

router = APIRouter(prefix="/me", tags=["account"])

AvatarColor = Literal[AVATAR_COLORS]  # type: ignore[valid-type]


class UsageOut(BaseModel):
    datasets: int
    storage_bytes: int
    profiled: int
    dashboards: int


class ProfileOut(BaseModel):
    username: str
    is_admin: bool
    display_name: str | None
    avatar_color: AvatarColor | None
    email_masked: str | None
    member_since: datetime
    usage: UsageOut


class ProfileUpdate(BaseModel):
    """Substitui nome e cor de uma vez. Campo vazio/ausente limpa o valor."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=MAX_DISPLAY_NAME * 2)
    avatar_color: AvatarColor | None = None

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if len(value) > MAX_DISPLAY_NAME:
            raise ValueError(f"O nome pode ter no máximo {MAX_DISPLAY_NAME} caracteres.")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("O nome não pode ter caracteres de controle.")
        return value


class LoginEventOut(BaseModel):
    success: bool
    browser: str
    created_at: datetime


@router.get("/profile", response_model=ProfileOut)
def read_profile(user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        return get_profile(conn, user)


@router.put("/profile", response_model=ProfileOut)
def save_profile(data: ProfileUpdate, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        update_profile(conn, user["id"], data.display_name, data.avatar_color)
        conn.commit()
        return get_profile(conn, user)


@router.get("/logins", response_model=list[LoginEventOut])
def recent_logins(user: dict = Depends(get_current_user)) -> list[dict]:
    """Os acessos recentes da própria conta (só data, resultado e navegador — sem IP)."""
    with get_connection() as conn:
        return list_login_events(conn, user["id"])


@router.post("/sessions/revoke-others", status_code=status.HTTP_204_NO_CONTENT)
def revoke_others(response: Response, user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        version = revoke_other_sessions(conn, user["id"])
        conn.commit()
    # As outras sessões deixam de valer; esta recebe um cookie com a versão nova.
    set_session_cookie(response, create_session_token(user["id"], version))
    logger.info("Outras sessões encerradas pelo próprio usuário: user_id=%s", user["id"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(data: ChangePasswordRequest, response: Response, user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],)).fetchone()

        # Exigir a senha atual impede que alguém com acesso a uma sessão aberta
        # (ex: computador destravado) troque a senha e tome a conta.
        if not verify_password(data.current_password, row["password_hash"]):
            logger.warning("Troca de senha recusada (senha atual incorreta): user_id=%s", user["id"])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta.")

        if data.new_password == data.current_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha precisa ser diferente da atual.")

        validate_new_password(data.new_password)

        updated = conn.execute(
            """
            UPDATE users
            SET password_hash = %s, session_version = session_version + 1
            WHERE id = %s
            RETURNING session_version
            """,
            (hash_password(data.new_password), user["id"]),
        ).fetchone()
        conn.execute(
            "INSERT INTO audit_logs (actor_user_id, action, target_user_id) VALUES (%s, 'change_own_password', %s)",
            (user["id"], user["id"]),
        )
        conn.commit()

    # Outras sessões ficam inválidas; esta recebe um cookie novo com a versão atual.
    set_session_cookie(response, create_session_token(user["id"], updated["session_version"]))
    logger.info("Senha trocada pelo próprio usuário: user_id=%s", user["id"])


# ---------- E-mail de verificação (o da própria conta) ----------


class EmailChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    current_password: str


class CodeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=32)


@router.post("/email/request")
def request_email_change(data: EmailChangeRequest, user: dict = Depends(get_current_user)) -> dict:
    """Passo 1: pede a troca. A senha atual é exigida (uma sessão aberta e esquecida não pode redirecionar os
    códigos de login para outro endereço) e o código vai para o endereço NOVO, para provar que ele é da pessoa."""
    limit_key = ("alterar-email", user["username"])
    if is_locked_out(limit_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitas tentativas. Aguarde um minuto.")

    with get_connection() as conn:
        row = conn.execute("SELECT password_hash, email FROM users WHERE id = %s", (user["id"],)).fetchone()
        if not verify_password(data.current_password, row["password_hash"]):
            register_failed_attempt(limit_key)
            logger.warning("Troca de e-mail recusada (senha incorreta): user_id=%s", user["id"])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta.")

        new_email = clean_email(data.email)
        if new_email == (row["email"] or "").lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este já é o seu e-mail atual.")
        ensure_email_free(conn, new_email, except_user_id=user["id"])

        try:
            code = issue_code(conn, user["id"], "email_change", new_email)
        except CodeCooldownError as exc:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Aguarde {exc.seconds_left} s para pedir outro código."
            )
        except TooManyCodesError:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitos códigos pedidos. Tente mais tarde.")
        conn.commit()

    subject, body = email_change_message(code)
    try:
        send_email(new_email, subject, body)
    except (MailNotConfiguredError, MailSendError):
        with get_connection() as conn:
            discard_code(conn, user["id"], "email_change")
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enviar o código para esse endereço agora. Confira o e-mail e tente de novo.",
        )
    logger.info("Código de troca de e-mail enviado: user_id=%s", user["id"])
    return {"email_hint": mask_email(new_email), "resend_in": RESEND_COOLDOWN_SECONDS}


@router.post("/email/confirm")
def confirm_email_change(data: CodeBody, user: dict = Depends(get_current_user)) -> dict:
    """Passo 2: o código enviado ao endereço novo confirma a troca."""
    with get_connection() as conn:
        try:
            new_email = check_code(conn, user["id"], "email_change", data.code)
            conn.commit()
        except CodeRejectedError as exc:
            conn.commit()  # guarda a tentativa contada (ou o código descartado)
            messages = {
                "wrong": f"Código incorreto. Você ainda tem {exc.attempts_left} tentativa(s).",
                "locked": "Muitas tentativas erradas. Peça um código novo.",
                "expired": "O código expirou. Peça um novo.",
                "missing": "Não há troca de e-mail pendente. Peça um código.",
            }
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=messages[exc.reason])

        ensure_email_free(conn, new_email, except_user_id=user["id"])  # pode ter sido usado por outra conta nesse meio-tempo
        old = conn.execute("SELECT email FROM users WHERE id = %s", (user["id"],)).fetchone()["email"]
        conn.execute("UPDATE users SET email = %s WHERE id = %s", (new_email, user["id"]))
        conn.execute(
            "INSERT INTO audit_logs (actor_user_id, action, target_user_id, details) VALUES (%s, 'change_own_email', %s, %s)",
            (user["id"], user["id"], f"{mask_email(old) or 'sem e-mail'} → {mask_email(new_email)}"),
        )
        conn.commit()
    logger.info("E-mail alterado pelo próprio usuário: user_id=%s", user["id"])
    return {"email_masked": mask_email(new_email)}


# ---------- Notificações dentro do sistema ----------


class NotificationOut(BaseModel):
    id: int
    kind: str
    message: str
    created_at: datetime
    read: bool


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("/notifications", response_model=NotificationsOut)
def my_notifications(user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        return list_notifications(conn, user["id"])


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
def read_notifications(user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        mark_all_read(conn, user["id"])
        conn.commit()
