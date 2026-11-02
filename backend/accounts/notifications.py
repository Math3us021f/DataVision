"""Avisos dentro do sistema, para a própria pessoa (ex.: "um administrador alterou o seu e-mail")."""

from django.utils import timezone

from accounts.models import Notification

MAX_LISTED = 20
KEEP_PER_USER = 100  # os mais antigos são apagados


def create_notification(user, kind: str, message: str) -> None:
    Notification.objects.create(user=user, kind=kind, message=message)
    keep = list(Notification.objects.filter(user=user).order_by("-id").values_list("id", flat=True)[:KEEP_PER_USER])
    Notification.objects.filter(user=user).exclude(id__in=keep).delete()


def list_notifications(user) -> dict:
    rows = Notification.objects.filter(user=user).order_by("-id")[:MAX_LISTED]
    items = [{"id": n.id, "kind": n.kind, "message": n.message, "created_at": n.created_at, "read": n.read_at is not None} for n in rows]
    unread = Notification.objects.filter(user=user, read_at__isnull=True).count()
    return {"items": items, "unread": unread}


def mark_all_read(user) -> None:
    Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=timezone.now())
