from fastapi import APIRouter, Depends

from src.core.auth import get_current_user
from src.core.db import get_connection

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        mine = conn.execute(
            """
            SELECT COUNT(*) AS datasets,
                   COALESCE(SUM(d.size_bytes), 0) AS storage_bytes,
                   COUNT(p.id) AS profiled
            FROM datasets d
            LEFT JOIN dataset_profiles p ON p.dataset_id = d.id
            WHERE d.owner_user_id = %s
            """,
            (user["id"],),
        ).fetchone()
        recent = conn.execute(
            """
            SELECT id, original_name, format, size_bytes, created_at
            FROM datasets
            WHERE owner_user_id = %s
            ORDER BY id DESC
            LIMIT 5
            """,
            (user["id"],),
        ).fetchall()

        # Contagem de uploads por dia nos últimos 7 dias (inclui hoje), para o gráfico da home.
        uploads_by_day = conn.execute(
            """
            SELECT gs.day::date AS day, COALESCE(c.count, 0) AS count
            FROM generate_series(CURRENT_DATE - INTERVAL '6 days', CURRENT_DATE, INTERVAL '1 day') AS gs(day)
            LEFT JOIN (
                SELECT created_at::date AS day, COUNT(*) AS count
                FROM datasets
                WHERE owner_user_id = %s AND created_at >= CURRENT_DATE - INTERVAL '6 days'
                GROUP BY created_at::date
            ) c ON c.day = gs.day::date
            ORDER BY gs.day
            """,
            (user["id"],),
        ).fetchall()

        result = {"mine": mine, "recent_datasets": recent, "uploads_by_day": uploads_by_day}

        # Só entra na resposta para admin: o usuário comum nunca recebe estes dados.
        if user["is_admin"]:
            result["admin"] = {
                "users": conn.execute(
                    """
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE is_active) AS active,
                           COUNT(*) FILTER (WHERE NOT is_active) AS inactive
                    FROM users
                    """
                ).fetchone(),
                "datasets_total": conn.execute("SELECT COUNT(*) AS total FROM datasets").fetchone()["total"],
                "recent_audit": conn.execute(
                    """
                    SELECT a.action, a.details, a.created_at,
                           actor.username AS actor, target.username AS target
                    FROM audit_logs a
                    LEFT JOIN users actor ON actor.id = a.actor_user_id
                    LEFT JOIN users target ON target.id = a.target_user_id
                    ORDER BY a.id DESC
                    LIMIT 8
                    """
                ).fetchall(),
            }

    return result
