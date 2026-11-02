"""Painel padrão: regras determinísticas que transformam o perfil salvo em specs de gráfico.

Função pura (só lê o dict do perfil) — nenhuma IA e nenhum acesso a dados aqui. Cada spec
devolvida é uma QuerySpec válida, executável por run_query().
"""

import re

from analytics.schemas import QuerySpec, WidgetSuggestion
from analytics.validator import NUMERIC

MAX_KPIS = 3
MAX_CATEGORY_CHARTS = 3
MAX_CATEGORY_DISTINCT = 50  # acima disso a coluna parece identificador/nome livre, não categoria
PIE_MAX_DISTINCT = 5
DAILY_MAX_DISTINCT = 31  # até ~1 mês de datas distintas: agrupar por mês daria 1 ponto só
IDENTIFIER_MIN_ROWS = 20

_ID_NAME = re.compile(r"(?:^|[_\s-])(?:id|cod|codigo|código)(?:$|[_\s-])", re.IGNORECASE)


def _is_identifier(column: dict, row_count: int) -> bool:
    """Colunas de identificador somadas/mediadas não significam nada, então não entram como medida."""
    if _ID_NAME.search(column["column_name"]):
        return True
    return (
        column["inferred_type"] == "integer"
        and column["null_count"] == 0
        and row_count >= IDENTIFIER_MIN_ROWS
        and column["distinct_count"] == row_count
    )


def _widget(title: str, spec: dict) -> WidgetSuggestion:
    return WidgetSuggestion(title=title, spec=QuerySpec.model_validate(spec))


def suggest_dashboard(profile: dict) -> list[WidgetSuggestion]:
    row_count = profile["row_count"]
    columns = profile["columns"]

    measures = [
        c for c in columns
        if c["inferred_type"] in NUMERIC and c["distinct_count"] > 0 and not _is_identifier(c, row_count)
    ]
    dates = [c for c in columns if c["inferred_type"] == "datetime" and c["distinct_count"] > 0]
    categories = [
        c for c in columns
        if c["inferred_type"] == "text" and 2 <= c["distinct_count"] <= MAX_CATEGORY_DISTINCT
        and c["distinct_count"] < row_count
    ]

    widgets: list[WidgetSuggestion] = []

    for measure in measures[:MAX_KPIS]:
        name = measure["column_name"]
        widgets.append(_widget(f"Soma de {name}", {"chart": "kpi", "metrics": [{"column": name, "agg": "sum"}]}))

    def default_metric(fallback_column: str) -> tuple[dict, str]:
        if measures:
            name = measures[0]["column_name"]
            return {"column": name, "agg": "sum"}, f"Soma de {name}"
        return {"column": fallback_column, "agg": "count"}, "Contagem"

    if dates:
        date_name = dates[0]["column_name"]
        grain, grain_label = ("day", "dia") if dates[0]["distinct_count"] <= DAILY_MAX_DISTINCT else ("month", "mês")
        metric, label = default_metric(date_name)
        widgets.append(_widget(
            f"{label} por {grain_label}",
            {"chart": "line", "dimension": {"column": date_name, "time_grain": grain}, "metrics": [metric]},
        ))

    for category in categories[:MAX_CATEGORY_CHARTS]:
        name = category["column_name"]
        metric, label = default_metric(name)
        chart = "pie" if category["distinct_count"] <= PIE_MAX_DISTINCT else "bar"
        widgets.append(_widget(
            f"{label} por {name}",
            {"chart": chart, "dimension": {"column": name}, "metrics": [metric]},
        ))

    return widgets
