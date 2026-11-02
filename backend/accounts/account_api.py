"""Minha conta: perfil, acessos, senha, sessões, e-mail de verificação e notificações."""

from datetime import datetime
from typing import Literal

from ninja import Router, Schema, Status
from pydantic import ConfigDict, Field, field_validator

from accounts import account, notifications
from accounts.auth import SessionAuth
from accounts.profile import AVATAR_COLORS

router = Router(tags=["minha conta"])
session_auth = SessionAuth()

MAX_DISPLAY_NAME = 60
AvatarColor = Literal[AVATAR_COLORS]  # type: ignore[valid-type]


class UsageOut(Schema):
    datasets: int
    storage_bytes: int
    profiled: int
    dashboards: int


class ProfileOut(Schema):
    username: str
    is_admin: bool
    display_name: str | None
    avatar_color: AvatarColor | None
    email_masked: str | None
    member_since: datetime
    usage: UsageOut


class ProfileUpdateIn(Schema):
    """Substitui nome e cor de uma vez. Campo vazio ou ausente limpa o valor."""

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


class LoginEventOut(Schema):
    success: bool
    browser: str
    created_at: datetime


class ChangePasswordIn(Schema):
    current_password: str
    new_password: str


class EmailChangeIn(Schema):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    current_password: str


class CodeIn(Schema):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=32)


class NotificationOut(Schema):
    id: int
    kind: str
    message: str
    created_at: datetime
    read: bool


class NotificationsOut(Schema):
    items: list[NotificationOut]
    unread: int


@router.get("/me/profile", auth=session_auth, response=ProfileOut, summary="Perfil e resumo de uso")
def read_profile(request):
    return account.get_profile(request.auth)


@router.put("/me/profile", auth=session_auth, response=ProfileOut, summary="Salva nome e cor do avatar")
def save_profile(request, data: ProfileUpdateIn):
    account.update_profile(request.auth, data.display_name, data.avatar_color)
    return account.get_profile(request.auth)


@router.get("/me/logins", auth=session_auth, response=list[LoginEventOut], summary="Acessos recentes (sem IP)")
def recent_logins(request):
    return account.list_login_events(request.auth)


@router.post("/me/sessions/revoke-others", auth=session_auth, response={204: None}, summary="Encerra as outras sessões")
def revoke_others(request):
    account.revoke_other_sessions(request)
    return Status(204, None)


@router.put("/me/password", auth=session_auth, response={204: None}, summary="Troca a própria senha")
def change_own_password(request, data: ChangePasswordIn):
    account.change_own_password(request, data.current_password, data.new_password)
    return Status(204, None)


@router.post("/me/email/request", auth=session_auth, summary="Pede a troca do e-mail (código ao endereço novo)")
def request_email_change(request, data: EmailChangeIn):
    return account.request_email_change(request.auth, data.email, data.current_password)


@router.post("/me/email/confirm", auth=session_auth, summary="Confirma a troca do e-mail com o código")
def confirm_email_change(request, data: CodeIn):
    return account.confirm_email_change(request.auth, data.code)


@router.get("/me/notifications", auth=session_auth, response=NotificationsOut, summary="Avisos do sistema para a conta")
def my_notifications(request):
    return notifications.list_notifications(request.auth)


@router.post("/me/notifications/read", auth=session_auth, response={204: None}, summary="Marca todos como lidos")
def read_notifications(request):
    notifications.mark_all_read(request.auth)
    return Status(204, None)
