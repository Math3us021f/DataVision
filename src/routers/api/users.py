from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.core.auth import require_admin
from src.core.db import get_connection
from src.services.users import (
    create_user as create_user_service,
    delete_user as delete_user_service,
    list_users_page,
    reset_user_password,
    set_user_active as set_user_active_service,
    set_user_email as set_user_email_service,
)

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False
    email: str | None = Field(default=None, max_length=254)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    email_masked: str | None = None  # nunca o e-mail inteiro


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def create_user(data: CreateUserRequest, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as conn:
        new_user = create_user_service(conn, admin["id"], data.username, data.password, data.is_admin, data.email)
        conn.commit()
    return new_user


@router.get("/summary")
def users_summary(admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE is_active) AS active,
                   COUNT(*) FILTER (WHERE NOT is_active) AS inactive,
                   COUNT(*) FILTER (WHERE is_admin) AS admins
            FROM users
            """
        ).fetchone()


@router.get("", response_model=UserPage)
def list_users(
    search: str = Query(default="", max_length=100),
    status_filter: Literal["all", "active", "inactive"] = Query(default="all", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
) -> dict:
    with get_connection() as conn:
        return list_users_page(conn, search, status_filter, page, page_size)


class UpdateActiveRequest(BaseModel):
    is_active: bool
    email_masked: str | None = None  # nunca o e-mail inteiro


@router.patch("/{user_id}", response_model=UserOut)
def set_user_active(user_id: int, data: UpdateActiveRequest, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as conn:
        updated = set_user_active_service(conn, admin["id"], user_id, data.is_active)
        conn.commit()
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, force: bool = Query(default=False), admin: dict = Depends(require_admin)) -> None:
    with get_connection() as conn:
        delete_user_service(conn, admin["id"], user_id, force)
        conn.commit()


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, data: ResetPasswordRequest, admin: dict = Depends(require_admin)) -> None:
    with get_connection() as conn:
        reset_user_password(conn, admin["id"], user_id, data.new_password)
        conn.commit()


class UpdateEmailRequest(BaseModel):
    email: str | None = Field(default=None, max_length=254)  # vazio ou nulo remove o e-mail


@router.patch("/{user_id}/email", response_model=UserOut)
def set_user_email(user_id: int, data: UpdateEmailRequest, admin: dict = Depends(require_admin)) -> dict:
    """Define ou remove o e-mail de outra conta (sem confirmação por e-mail; a pessoa é avisada no sistema)."""
    with get_connection() as conn:
        updated = set_user_email_service(conn, admin["id"], user_id, data.email)
        conn.commit()
    return updated
