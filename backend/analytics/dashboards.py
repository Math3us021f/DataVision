"""Dashboard salvo de um dataset (um por dataset). O dono já foi verificado por quem chama."""

import logging
from typing import Any

from analytics.schemas import DashboardSpec
from analytics.validator import ColumnTypes, validate_query
from datasets.models import Dashboard, Dataset

logger = logging.getLogger("datavision")


def validate_dashboard(spec: DashboardSpec, types: ColumnTypes) -> None:
    """Cada gráfico, junto com os filtros globais, precisa ser uma consulta válida para este dataset.
    Levanta InvalidQueryError (a rota converte em 422)."""
    for widget in spec.widgets:
        validate_query(widget.model_copy(update={"filters": [*widget.filters, *spec.filters]}), types)


def _out(dashboard: Dashboard) -> dict[str, Any]:
    return {**dashboard.spec, "updated_at": dashboard.updated_at}


def get_saved_dashboard(dataset: Dataset) -> dict[str, Any] | None:
    dashboard = Dashboard.objects.filter(dataset=dataset).first()
    return _out(dashboard) if dashboard else None


def save_dashboard(dataset: Dataset, owner, spec: DashboardSpec) -> dict[str, Any]:
    dashboard, _ = Dashboard.objects.update_or_create(
        dataset=dataset, defaults={"owner": owner, "spec": spec.model_dump(mode="json")}
    )
    logger.info("Dashboard salvo: dataset_id=%s owner_id=%s widgets=%s", dataset.pk, owner.pk, len(spec.widgets))
    return _out(dashboard)


def delete_saved_dashboard(dataset: Dataset) -> None:
    Dashboard.objects.filter(dataset=dataset).delete()
