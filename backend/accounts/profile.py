"""Perfil do próprio usuário: cores do avatar e dados exibidos."""

from typing import Any

# Cores do avatar de iniciais. A interface mapeia cada nome para uma cor; o servidor só aceita estes valores.
AVATAR_COLORS = ("orange", "green", "blue", "violet", "rose", "amber", "teal", "slate")


def avatar_color_of(preferences: dict[str, Any] | None) -> str | None:
    color = (preferences or {}).get("avatar_color")
    return color if color in AVATAR_COLORS else None
