from analytics.schemas import FilterSpec, MetricSpec, QuerySpec

ColumnTypes = dict[str, str]  # nome da coluna -> inferred_type do perfil

NUMERIC = frozenset({"integer", "float"})
ORDERABLE = NUMERIC | {"datetime"}


class InvalidQueryError(ValueError):
    """Spec incompatível com o dataset. O router converte em HTTP 422."""


def _column_type(column: str, types: ColumnTypes) -> str:
    try:
        return types[column]
    except KeyError:
        raise InvalidQueryError(f"Coluna inexistente: {column!r}") from None


def _validate_metric(metric: MetricSpec, types: ColumnTypes) -> None:
    col_type = _column_type(metric.column, types)
    if metric.agg in ("sum", "mean", "min", "max") and col_type not in NUMERIC:
        raise InvalidQueryError(f"{metric.agg!r} exige coluna numérica; {metric.column!r} é {col_type}")


def _validate_filter(flt: FilterSpec, types: ColumnTypes) -> None:
    col_type = _column_type(flt.column, types)
    if flt.op in ("gt", "gte", "lt", "lte") and col_type not in ORDERABLE:
        raise InvalidQueryError(f"{flt.op!r} exige coluna numérica ou de data; {flt.column!r} é {col_type}")
    if flt.op == "contains" and col_type != "text":
        raise InvalidQueryError(f"'contains' só vale para texto; {flt.column!r} é {col_type}")
    if (flt.op == "in") != isinstance(flt.value, list):
        raise InvalidQueryError("'in' exige uma lista; os demais operadores exigem um valor único")


def validate_query(spec: QuerySpec, types: ColumnTypes) -> None:
    if spec.dimension is not None:
        dim_type = _column_type(spec.dimension.column, types)
        if spec.dimension.time_grain is not None and dim_type != "datetime":
            raise InvalidQueryError("time_grain só vale para colunas de data")
    for metric in spec.metrics:
        _validate_metric(metric, types)
    for flt in spec.filters:
        _validate_filter(flt, types)
