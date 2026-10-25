from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.auth import hash_password, require_admin, validate_new_password
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


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def create_user(data: CreateUserRequest, admin: dict = Depends(require_admin)) -> dict:
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome de usuário.")
    validate_new_password(data.password)

    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nome de usuário já existe")

        new_user = conn.execute(
            """
            INSERT INTO users (username, password_hash, is_admin)
            VALUES (%s, %s, %s)
            RETURNING id, username, is_admin, is_active
            """,
            (username, hash_password(data.password), data.is_admin),
        ).fetchone()

        log_action(conn, admin["id"], "create_user", target_user_id=new_user["id"])
        conn.commit()

    logger.info("Usuário criado: id=%s username=%r por admin_id=%s", new_user["id"], username, admin["id"])
    return new_user


@router.get("", response_model=UserPage)
def list_users(
    search: str = Query(default="", max_length=100),
    status_filter: Literal["all", "active", "inactive"] = Query(default="all", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
) -> dict:
    conditions = []
    params: list = []

    if search.strip():
        # ILIKE com parâmetro: o texto do usuário nunca é concatenado no SQL.
        # Escapamos % e _ para que sejam buscados literalmente, não como curingas.
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append("username ILIKE %s")
        params.append(f"%{escaped}%")

    if status_filter == "active":
        conditions.append("is_active")
    elif status_filter == "inactive":
        conditions.append("NOT is_active")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS total FROM users {where}", params).fetchone()["total"]
        items = conn.execute(
            f"""
            SELECT id, username, is_admin, is_active FROM users {where}
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()

    return {"items": items, "total": total, "page": page, "page_size": page_size}


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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: dict = Depends(require_admin)) -> None:
    if user_id == admin["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode excluir a própria conta")

    with get_connection() as conn:
        target = conn.execute("SELECT id, username FROM users WHERE id = %s", (user_id,)).fetchone()
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

        # Apagar datasets exigiria apagar também os arquivos no MinIO e os perfilamentos:
        # exclusão de dados em cascata fica fora do escopo. Nesse caso, a saída é desativar.
        dataset_count = conn.execute(
            "SELECT COUNT(*) AS total FROM datasets WHERE owner_user_id = %s", (user_id,)
        ).fetchone()["total"]
        if dataset_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Este usuário possui {dataset_count} dataset(s) e não pode ser excluído. Desative a conta em vez disso.",
            )

        conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
        # target_user_id fica vazio (o usuário não existe mais); id e nome vão em details.
        log_action(conn, admin["id"], "delete_user", details=f"id={target['id']} username={target['username']!r}")
        conn.commit()

    logger.info("delete_user: id=%s username=%r por admin_id=%s", target["id"], target["username"], admin["id"])


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(user_id: int, data: ResetPasswordRequest, admin: dict = Depends(require_admin)) -> None:
    validate_new_password(data.new_password)

    with get_connection() as conn:
        updated = conn.execute(
            """
            UPDATE users
            SET password_hash = %s, session_version = session_version + 1
            WHERE id = %s
            RETURNING id
            """,
            (hash_password(data.new_password), user_id),
        ).fetchone()

        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

        log_action(conn, admin["id"], "reset_password", target_user_id=user_id)
        conn.commit()

    logger.info("reset_password: id=%s por admin_id=%s", user_id, admin["id"])
