"""Dashboard salvo de um dataset (um por dataset). O dono já foi verificado por quem chama."""

from typing import Any

from psycopg.types.json import Jsonb

from src.core.logging_config import logger
from src.schemas.analytics import DashboardSpec
from src.services.analytics.validator import ColumnTypes, validate_query


def validate_dashboard(spec: DashboardSpec, types: ColumnTypes) -> None:
    """Cada gráfico, junto com os filtros globais, precisa ser uma consulta válida para este dataset.
    Levanta InvalidQueryError (o router converte em 422)."""
    for widget in spec.widgets:
        validate_query(widget.model_copy(update={"filters": [*widget.filters, *spec.filters]}), types)


def get_saved_dashboard(conn, dataset_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT spec, updated_at FROM dashboards WHERE dataset_id = %s", (dataset_id,)
    ).fetchone()
    if row is None:
        return None
    return {**row["spec"], "updated_at": row["updated_at"]}


def save_dashboard(conn, dataset_id: int, owner_user_id: int, spec: DashboardSpec) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO dashboards (dataset_id, owner_user_id, spec)
        VALUES (%s, %s, %s)
        ON CONFLICT (dataset_id) DO UPDATE SET spec = EXCLUDED.spec, updated_at = now()
        RETURNING spec, updated_at
        """,
        (dataset_id, owner_user_id, Jsonb(spec.model_dump(mode="json"))),
    ).fetchone()
    logger.info(
        "Dashboard salvo: dataset_id=%s owner_id=%s widgets=%s", dataset_id, owner_user_id, len(spec.widgets)
    )
    return {**row["spec"], "updated_at": row["updated_at"]}


def delete_saved_dashboard(conn, dataset_id: int) -> None:
    conn.execute("DELETE FROM dashboards WHERE dataset_id = %s", (dataset_id,))
