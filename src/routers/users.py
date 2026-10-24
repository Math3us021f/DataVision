from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth import hash_password, require_admin
from src.db import get_connection
from src.logging_config import logger

router = APIRouter(prefix="/users", tags=["users"])


def log_action(conn, actor_user_id: int, action: str, target_user_id: int | None = None, details: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_logs (actor_user_id, action, target_user_id, details) VALUES (%s, %s, %s, %s)",
        (actor_user_id, action, target_user_id, details),
    )


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def create_user(data: CreateUserRequest, admin: dict = Depends(require_admin)) -> dict:
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = %s", (data.username,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nome de usuário já existe")

        new_user = conn.execute(
            """
            INSERT INTO users (username, password_hash, is_admin)
            VALUES (%s, %s, %s)
            RETURNING id, username, is_admin, is_active
            """,
            (data.username, hash_password(data.password), data.is_admin),
        ).fetchone()

        log_action(conn, admin["id"], "create_user", target_user_id=new_user["id"])
        conn.commit()

    logger.info("Usuário criado: id=%s username=%r por admin_id=%s", new_user["id"], data.username, admin["id"])
    return new_user


@router.get("", response_model=list[UserOut])
def list_users(admin: dict = Depends(require_admin)) -> list[dict]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, username, is_admin, is_active FROM users ORDER BY id"
        ).fetchall()


class UpdateActiveRequest(BaseModel):
    is_active: bool


@router.patch("/{user_id}", response_model=UserOut)
def set_user_active(user_id: int, data: UpdateActiveRequest, admin: dict = Depends(require_admin)) -> dict:
    if user_id == admin["id"] and not data.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode desativar a própria conta")

    with get_connection() as conn:
        updated = conn.execute(
            """
            UPDATE users SET is_active = %s WHERE id = %s
            RETURNING id, username, is_admin, is_active
            """,
            (data.is_active, user_id),
        ).fetchone()

        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

        action = "activate_user" if data.is_active else "deactivate_user"
        log_action(conn, admin["id"], action, target_user_id=user_id)
        conn.commit()

    logger.info("%s: id=%s por admin_id=%s", action, user_id, admin["id"])
    return updated
