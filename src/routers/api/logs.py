from fastapi import APIRouter, Depends, Query

from src.core.auth import require_admin
from src.core.logging_config import LOG_FILE_PATH, read_log_tail

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/app")
def read_app_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    admin: dict = Depends(require_admin),
) -> dict:
    """Devolve as últimas `limit` linhas do log da aplicação. Caminho do arquivo é fixo no código."""
    return {"lines": read_log_tail(LOG_FILE_PATH, limit)}
