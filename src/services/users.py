"""Regras de negócio de gestão de usuários: criação, busca, ativação e exclusão.

Os routers em src/routers/api/users.py ficam só com a camada HTTP (validação de
entrada via Pydantic, códigos de status) e chamam estas funções para o resto.
"""

from typing import Literal

from fastapi import HTTPException, status

from src.core.auth import hash_password, validate_new_password
from src.core.logging_config import logger
from src.services.datasets import delete_dataset_core
from src.services.notifications import create_notification
from src.services.verification import InvalidEmailError, mask_email, normalize_email

EMAIL_IN_USE = HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail já está em uso por outra conta.")


def public_user(row: dict) -> dict:
    """O que a API mostra de um usuário: nunca o e-mail inteiro, só a versão mascarada."""
    shown = {key: value for key, value in row.items() if key != "email"}
    shown["email_masked"] = mask_email(row.get("email"))
    return shown


def clean_email(raw: str) -> str:
    try:
        return normalize_email(raw)
    except InvalidEmailError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def ensure_email_free(conn, email: str, except_user_id: int | None = None) -> None:
    row = conn.execute(
        "SELECT id FROM users WHERE lower(email) = %s AND id IS DISTINCT FROM %s", (email, except_user_id)
    ).fetchone()
    if row is not None:
        raise EMAIL_IN_USE


def log_action(conn, actor_user_id: int, action: str, target_user_id: int | None = None, details: str | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_logs (actor_user_id, action, target_user_id, details) VALUES (%s, %s, %s, %s)",
        (actor_user_id, action, target_user_id, details),
    )


def create_user(conn, admin_id: int, username: str, password: str, is_admin: bool, email: str | None = None) -> dict:
    username = username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe o nome de usuário.")
    validate_new_password(password)
    email = clean_email(email) if email and email.strip() else None

    existing = conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nome de usuário já existe")
    if email:
        ensure_email_free(conn, email)

    new_user = conn.execute(
        """
        INSERT INTO users (username, password_hash, is_admin, email)
        VALUES (%s, %s, %s, %s)
        RETURNING id, username, is_admin, is_active, email
        """,
        (username, hash_password(password), is_admin, email),
    ).fetchone()

    log_action(
        conn, admin_id, "create_user", target_user_id=new_user["id"],
        details=f"com e-mail {mask_email(email)}" if email else None,
    )

    logger.info("Usuário criado: id=%s username=%r por admin_id=%s", new_user["id"], username, admin_id)
    return public_user(new_user)


def list_users_page(
    conn,
    search: str,
    status_filter: Literal["all", "active", "inactive"],
    page: int,
    page_size: int,
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

    total = conn.execute(f"SELECT COUNT(*) AS total FROM users {where}", params).fetchone()["total"]
    items = conn.execute(
        f"""
        SELECT id, username, is_admin, is_active, email FROM users {where}
        ORDER BY id
        LIMIT %s OFFSET %s
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()

    return {"items": [public_user(item) for item in items], "total": total, "page": page, "page_size": page_size}


def set_user_active(conn, admin_id: int, user_id: int, is_active: bool) -> dict:
    if user_id == admin_id and not is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode desativar a própria conta")

    updated = conn.execute(
        """
        UPDATE users SET is_active = %s WHERE id = %s
        RETURNING id, username, is_admin, is_active, email
        """,
        (is_active, user_id),
    ).fetchone()

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    action = "activate_user" if is_active else "deactivate_user"
    log_action(conn, admin_id, action, target_user_id=user_id)

    logger.info("%s: id=%s por admin_id=%s", action, user_id, admin_id)
    return public_user(updated)


def set_user_email(conn, admin_id: int, user_id: int, new_email: str | None) -> dict:
    """O administrador define ou remove o e-mail de outra conta, sem confirmação por e-mail. Fica na
    auditoria e a pessoa é avisada por uma notificação dentro do sistema. Remover o e-mail desliga o
    segundo passo dessa conta; por isso o administrador não pode mexer no PRÓPRIO e-mail por aqui
    (isso passa pela confirmação em "Minha conta")."""
    if user_id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Para alterar o seu próprio e-mail use "Minha conta", que confirma o endereço por um código.',
        )
    target = conn.execute("SELECT id, email FROM users WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    email = clean_email(new_email) if new_email and new_email.strip() else None
    if email:
        ensure_email_free(conn, email, except_user_id=user_id)

    updated = conn.execute(
        "UPDATE users SET email = %s WHERE id = %s RETURNING id, username, is_admin, is_active, email", (email, user_id)
    ).fetchone()
    conn.execute("DELETE FROM email_codes WHERE user_id = %s", (user_id,))  # códigos pendentes eram para o e-mail antigo

    before = mask_email(target["email"]) or "sem e-mail"
    after = mask_email(email) or "removido"
    log_action(conn, admin_id, "admin_change_email", target_user_id=user_id, details=f"{before} → {after}")
    message = (
        f"Um administrador alterou o seu e-mail de verificação para {after}."
        if email
        else "Um administrador removeu o seu e-mail de verificação. Sem ele, o login volta a pedir só a senha."
    )
    create_notification(conn, user_id, "email_changed_by_admin", message)

    logger.info("admin_change_email: id=%s por admin_id=%s", user_id, admin_id)
    return public_user(updated)


def delete_user(conn, admin_id: int, user_id: int, force: bool) -> None:
    if user_id == admin_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode excluir a própria conta")

    target = conn.execute("SELECT id, username FROM users WHERE id = %s", (user_id,)).fetchone()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    datasets = conn.execute(
        "SELECT id, object_key FROM datasets WHERE owner_user_id = %s", (user_id,)
    ).fetchall()

    if datasets and not force:
        # Sem ?force=true, excluir fica bloqueado: apagar datasets é irreversível
        # (arquivo no MinIO junto), então exige uma confirmação explícita à parte.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Este usuário possui {len(datasets)} dataset(s). Excluir também vai apagar "
                "os arquivos no MinIO, de forma irreversível. Confirme para prosseguir, ou "
                "desative a conta em vez disso."
            ),
        )

    if datasets:
        for dataset in datasets:
            delete_dataset_core(conn, dataset["id"], dataset["object_key"])
        log_action(
            conn, admin_id, "force_delete_user_datasets",
            target_user_id=user_id, details=f"{len(datasets)} dataset(s) apagados",
        )

    conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
    # target_user_id fica vazio (o usuário não existe mais); id e nome vão em details.
    log_action(conn, admin_id, "delete_user", details=f"id={target['id']} username={target['username']!r}")

    logger.info(
        "delete_user: id=%s username=%r por admin_id=%s datasets_apagados=%s",
        target["id"], target["username"], admin_id, len(datasets),
    )


def reset_user_password(conn, admin_id: int, user_id: int, new_password: str) -> None:
    validate_new_password(new_password)

    updated = conn.execute(
        """
        UPDATE users
        SET password_hash = %s, session_version = session_version + 1
        WHERE id = %s
        RETURNING id
        """,
        (hash_password(new_password), user_id),
    ).fetchone()

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    log_action(conn, admin_id, "reset_password", target_user_id=user_id)

    logger.info("reset_password: id=%s por admin_id=%s", user_id, admin_id)
