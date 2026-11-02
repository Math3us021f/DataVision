from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.core.auth import require_admin
from src.core.db import get_connection
from src.services.audit import KNOWN_ACTIONS, list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit"])

AllowedAction = Literal[
    "", "create_user", "activate_user", "deactivate_user", "delete_user",
    "force_delete_user_datasets", "reset_password", "change_own_password", "revoke_other_sessions",
]


class AuditLogOut(BaseModel):
    id: int
    action: str
    details: str | None
    created_at: datetime
    actor_username: str | None
    target_username: str | None


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditLogPage)
def list_audit(
    search: str = Query(default="", max_length=100),
    action: AllowedAction = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
) -> dict:
    with get_connection() as conn:
        return list_audit_logs(conn, search, action, page, page_size)


@router.get("/actions", response_model=list[str])
def list_actions(admin: dict = Depends(require_admin)) -> list[str]:
    return KNOWN_ACTIONS
