"""Auditoria: registra as ações administrativas e consulta o histórico."""

from django.db.models import Q

from audit.models import AuditLog

KNOWN_ACTIONS = [value for value, _ in AuditLog.Action.choices]


def log_action(actor, action: str, target=None, details: str | None = None) -> None:
    AuditLog.objects.create(actor=actor, action=action, target=target, details=details)


def list_audit_logs(search: str, action: str, page: int, page_size: int) -> dict:
    logs = AuditLog.objects.select_related("actor", "target")
    if search.strip():
        # icontains escapa % e _ sozinho: o que a pessoa digita é buscado literalmente, nunca como curinga.
        term = search.strip()
        logs = logs.filter(Q(actor__username__icontains=term) | Q(target__username__icontains=term))
    if action.strip():
        logs = logs.filter(action=action)

    total = logs.count()
    rows = logs.order_by("-id")[(page - 1) * page_size : page * page_size]
    items = [
        {
            "id": row.id,
            "action": row.action,
            "details": row.details,
            "created_at": row.created_at,
            "actor_username": row.actor.username if row.actor else None,
            "target_username": row.target.username if row.target else None,
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
