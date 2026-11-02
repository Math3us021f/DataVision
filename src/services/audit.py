"""Consulta paginada de audit_logs, com busca por usuário e filtro por ação."""

KNOWN_ACTIONS = [
    "create_user",
    "activate_user",
    "deactivate_user",
    "delete_user",
    "force_delete_user_datasets",
    "reset_password",
    "change_own_password",
    "revoke_other_sessions",
]


def list_audit_logs(conn, search: str, action: str, page: int, page_size: int) -> dict:
    conditions = []
    params: list = []

    if search.strip():
        # ILIKE com parâmetro: o texto do usuário nunca é concatenado no SQL.
        # Escapamos % e _ para que sejam buscados literalmente, não como curingas.
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append("(actor.username ILIKE %s OR target.username ILIKE %s)")
        params.extend([f"%{escaped}%", f"%{escaped}%"])

    if action.strip():
        conditions.append("audit_logs.action = %s")
        params.append(action)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    from_clause = f"""
        FROM audit_logs
        LEFT JOIN users actor ON actor.id = audit_logs.actor_user_id
        LEFT JOIN users target ON target.id = audit_logs.target_user_id
        {where}
    """

    total = conn.execute(f"SELECT COUNT(*) AS total {from_clause}", params).fetchone()["total"]
    items = conn.execute(
        f"""
        SELECT audit_logs.id, audit_logs.action, audit_logs.details, audit_logs.created_at,
               actor.username AS actor_username, target.username AS target_username
        {from_clause}
        ORDER BY audit_logs.id DESC
        LIMIT %s OFFSET %s
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()

    return {"items": items, "total": total, "page": page, "page_size": page_size}
