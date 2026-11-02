"""Números do painel inicial. Os dados de administração só entram para administradores."""

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from datasets.models import Dataset


def build_summary(user: User) -> dict:
    mine = Dataset.objects.filter(owner=user)
    totals = mine.aggregate(datasets=Count("id"), storage_bytes=Coalesce(Sum("size_bytes"), 0), profiled=Count("profile"))
    recent = mine.order_by("-id")[:5].values("id", "original_name", "format", "size_bytes", "created_at")

    # Envios por dia nos últimos 7 dias (inclui hoje); dias sem envio aparecem com zero.
    today = timezone.localdate()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    counts = {
        row["day"]: row["total"]
        for row in mine.filter(created_at__date__gte=days[0]).annotate(day=TruncDate("created_at")).values("day").annotate(total=Count("id"))
    }

    result = {
        "mine": totals,
        "recent_datasets": list(recent),
        "uploads_by_day": [{"day": day.isoformat(), "count": counts.get(day, 0)} for day in days],
    }

    # Só entra na resposta para admin: o usuário comum nunca recebe estes dados.
    if user.is_admin:
        audit = AuditLog.objects.select_related("actor", "target").order_by("-id")[:8]
        result["admin"] = {
            "users": User.objects.aggregate(
                total=Count("id"), active=Count("id", filter=Q(is_active=True)), inactive=Count("id", filter=Q(is_active=False))
            ),
            "datasets_total": Dataset.objects.count(),
            "recent_audit": [
                {
                    "action": a.action,
                    "details": a.details,
                    "created_at": a.created_at,
                    "actor": a.actor.username if a.actor else None,
                    "target": a.target.username if a.target else None,
                }
                for a in audit
            ],
        }
    return result
