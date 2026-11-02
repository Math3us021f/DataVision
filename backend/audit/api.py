"""Histórico das ações administrativas (só administradores)."""

from datetime import datetime
from typing import Literal

from ninja import Query, Router, Schema
from pydantic import Field

from accounts.auth import AdminAuth
from audit.models import AuditLog
from audit.services import KNOWN_ACTIONS, list_audit_logs

router = Router(tags=["auditoria"])
admin = AdminAuth()

ActionFilter = Literal[tuple([""] + [value for value, _ in AuditLog.Action.choices])]  # type: ignore[valid-type]


class AuditLogOut(Schema):
    id: int
    action: str
    details: str | None
    created_at: datetime
    actor_username: str | None
    target_username: str | None


class AuditLogPage(Schema):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


class AuditParams(Schema):
    search: str = Field(default="", max_length=100)
    action: ActionFilter = ""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


@router.get("/audit-logs", auth=admin, response=AuditLogPage, summary="Histórico (mais recentes primeiro)")
def audit_logs(request, params: Query[AuditParams]):
    return list_audit_logs(params.search, params.action, params.page, params.page_size)


@router.get("/audit-logs/actions", auth=admin, response=list[str], summary="Ações conhecidas (para o filtro)")
def audit_actions(request):
    return KNOWN_ACTIONS
