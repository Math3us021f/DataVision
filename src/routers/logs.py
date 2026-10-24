from fastapi import APIRouter, Depends, Query

from src.auth import require_admin
from src.logging_config import LOG_FILE_PATH

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/app")
def read_app_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    admin: dict = Depends(require_admin),
) -> dict:
    """Devolve as últimas `limit` linhas do log da aplicação. Caminho do arquivo é fixo no código."""
    try:
        with open(LOG_FILE_PATH, encoding="utf-8") as log_file:
            lines = log_file.readlines()
    except FileNotFoundError:
        lines = []

    return {"lines": [line.rstrip("\n") for line in lines[-limit:]]}
