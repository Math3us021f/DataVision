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
from src.services.account import (
    AVATAR_COLORS,
    MAX_DISPLAY_NAME,
    get_profile,
    list_login_events,
    revoke_other_sessions,
    update_profile,
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
