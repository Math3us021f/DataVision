"""Conta do próprio usuário: perfil, resumo de uso, acessos recentes e encerramento de outras sessões."""

from typing import Any

from psycopg.types.json import Jsonb

from src.services.verification import mask_email

# Cores do avatar de iniciais. A interface mapeia cada nome para uma cor; o servidor só aceita estes valores.
AVATAR_COLORS = ("orange", "green", "blue", "violet", "rose", "amber", "teal", "slate")
MAX_DISPLAY_NAME = 60
MAX_LOGIN_EVENTS = 50  # retenção por usuário: os mais antigos são apagados

_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (
    ("Windows", "Windows"),
    ("Android", "Android"),
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)


def summarize_user_agent(user_agent: str | None) -> str:
    """"Chrome · Windows". Só este resumo é guardado: nem o texto original do navegador nem o IP."""
    if not user_agent:
        return "Desconhecido"
    browser = next((name for marker, name in _BROWSERS if marker in user_agent), "Outro navegador")
    system = next((name for marker, name in _SYSTEMS if marker in user_agent), "sistema desconhecido")
    return f"{browser} · {system}"


def avatar_color_of(preferences: dict[str, Any] | None) -> str | None:
    color = (preferences or {}).get("avatar_color")
    return color if color in AVATAR_COLORS else None


def get_profile(conn, user: dict) -> dict[str, Any]:
    usage = conn.execute(
        """
        SELECT COUNT(*) AS datasets,
               COALESCE(SUM(d.size_bytes), 0) AS storage_bytes,
               COUNT(p.id) AS profiled,
               (SELECT COUNT(*) FROM dashboards b WHERE b.owner_user_id = %s) AS dashboards
        FROM datasets d
        LEFT JOIN dataset_profiles p ON p.dataset_id = d.id
        WHERE d.owner_user_id = %s
        """,
        (user["id"], user["id"]),
    ).fetchone()
    created_at = conn.execute("SELECT created_at FROM users WHERE id = %s", (user["id"],)).fetchone()["created_at"]
    row = conn.execute("SELECT display_name, preferences, email FROM users WHERE id = %s", (user["id"],)).fetchone()
    return {
        "username": user["username"],
        "is_admin": user["is_admin"],
        "display_name": row["display_name"],
        "avatar_color": avatar_color_of(row["preferences"]),
        "email_masked": mask_email(row["email"]),
        "member_since": created_at,
        "usage": usage,
    }


def update_profile(conn, user_id: int, display_name: str | None, avatar_color: str | None) -> None:
    preferences = {"avatar_color": avatar_color} if avatar_color else {}
    conn.execute(
        "UPDATE users SET display_name = %s, preferences = %s WHERE id = %s",
        (display_name, Jsonb(preferences), user_id),
    )


def record_login_event(conn, user_id: int, success: bool, user_agent: str | None) -> None:
    conn.execute(
        "INSERT INTO login_events (user_id, success, browser) VALUES (%s, %s, %s)",
        (user_id, success, summarize_user_agent(user_agent)),
    )
    conn.execute(
        """
        DELETE FROM login_events
        WHERE user_id = %s AND id NOT IN (
            SELECT id FROM login_events WHERE user_id = %s ORDER BY id DESC LIMIT %s
        )
        """,
        (user_id, user_id, MAX_LOGIN_EVENTS),
    )


def list_login_events(conn, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return conn.execute(
        "SELECT success, browser, created_at FROM login_events WHERE user_id = %s ORDER BY id DESC LIMIT %s",
        (user_id, limit),
    ).fetchall()


def revoke_other_sessions(conn, user_id: int) -> int:
    """Incrementa a versão de sessão: todo cookie emitido antes deixa de valer. Devolve a versão nova."""
    row = conn.execute(
        "UPDATE users SET session_version = session_version + 1 WHERE id = %s RETURNING session_version",
        (user_id,),
    ).fetchone()
    conn.execute(
        "INSERT INTO audit_logs (actor_user_id, action, target_user_id) VALUES (%s, 'revoke_other_sessions', %s)",
        (user_id, user_id),
    )
    return row["session_version"]
