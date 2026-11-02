"""Avisos dentro do sistema, para a própria pessoa (ex.: "um administrador alterou o seu e-mail")."""

MAX_LISTED = 20
KEEP_PER_USER = 100  # os mais antigos são apagados


def create_notification(conn, user_id: int, kind: str, message: str) -> None:
    conn.execute("INSERT INTO notifications (user_id, kind, message) VALUES (%s, %s, %s)", (user_id, kind, message))
    conn.execute(
        """
        DELETE FROM notifications
        WHERE user_id = %s AND id NOT IN (SELECT id FROM notifications WHERE user_id = %s ORDER BY id DESC LIMIT %s)
        """,
        (user_id, user_id, KEEP_PER_USER),
    )


def list_notifications(conn, user_id: int) -> dict:
    items = conn.execute(
        """
        SELECT id, kind, message, created_at, read_at IS NOT NULL AS read
        FROM notifications WHERE user_id = %s ORDER BY id DESC LIMIT %s
        """,
        (user_id, MAX_LISTED),
    ).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) AS total FROM notifications WHERE user_id = %s AND read_at IS NULL", (user_id,)
    ).fetchone()["total"]
    return {"items": items, "unread": unread}


def mark_all_read(conn, user_id: int) -> None:
    conn.execute("UPDATE notifications SET read_at = now() WHERE user_id = %s AND read_at IS NULL", (user_id,))
