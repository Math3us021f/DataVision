import operator
from typing import Any

import pandas as pd

from src.schemas.analytics import FilterSpec, QuerySpec, Scalar
from src.services.analytics.validator import NUMERIC, ColumnTypes, InvalidQueryError, validate_query
from src.services.profiling import parse_datetimes

# Nome vindo do cliente nunca vira nome de método: só chaves deste dicionário chegam ao Pandas.
AGG_FUNCS = {"sum": "sum", "mean": "mean", "count": "count", "min": "min", "max": "max", "count_distinct": "nunique"}
AGG_LABELS = {"sum": "Soma", "mean": "Média", "count": "Contagem", "min": "Mínimo", "max": "Máximo", "count_distinct": "Distintos"}
TIME_FORMATS = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}
COMPARISONS = {"eq": operator.eq, "ne": operator.ne, "gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le}


def prepare_dataframe(df: pd.DataFrame, types: ColumnTypes) -> pd.DataFrame:
    datetime_cols = [c for c, t in types.items() if t == "datetime" and c in df.columns]
    if not datetime_cols:
        return df
    prepared = df.copy(deep=False)  # não altera o DataFrame original
    for col in datetime_cols:
        prepared[col] = parse_datetimes(prepared[col].astype(str))
    return prepared


def _coerce(value: Scalar, col_type: str, column: str) -> Any:
    try:
        if col_type in NUMERIC:
            if isinstance(value, bool):
                raise TypeError("booleano não é número")
            return float(value)
        if col_type == "datetime":
            return pd.Timestamp(value)
        if col_type == "boolean":
            if not isinstance(value, bool):
                raise TypeError("esperado true/false")
            return value
        return str(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidQueryError(f"Valor inválido para a coluna {column!r} ({col_type}): {exc}") from exc


def _filter_mask(df: pd.DataFrame, flt: FilterSpec, types: ColumnTypes) -> pd.Series:
    series, col_type = df[flt.column], types[flt.column]
    if flt.op == "in":
        return series.isin([_coerce(v, col_type, flt.column) for v in flt.value])
    value = _coerce(flt.value, col_type, flt.column)
    if flt.op == "contains":  # regex=False: o texto do usuário nunca é interpretado como expressão regular
        return series.astype("string").str.contains(str(value), case=False, regex=False, na=False)
    return COMPARISONS[flt.op](series, value) & series.notna()


def _apply_filters(df: pd.DataFrame, spec: QuerySpec, types: ColumnTypes) -> pd.DataFrame:
    if not spec.filters:
        return df
    mask = pd.Series(True, index=df.index)
    for flt in spec.filters:
        mask &= _filter_mask(df, flt, types)
    return df[mask]


def _group_key(df: pd.DataFrame, spec: QuerySpec) -> pd.Series:
    assert spec.dimension is not None
    series = df[spec.dimension.column]
    if spec.dimension.time_grain:
        return series.dt.strftime(TIME_FORMATS[spec.dimension.time_grain])  # rótulo ISO: ordena como texto
    return series


def _number(value: Any) -> float | None:
    return None if pd.isna(value) else float(value)


def run_query(df: pd.DataFrame, spec: QuerySpec, types: ColumnTypes) -> dict[str, Any]:
    validate_query(spec, types)
    filtered = _apply_filters(prepare_dataframe(df, types), spec, types)
    base = {"total_rows_matched": len(filtered), "truncated": False}

    if spec.chart == "kpi":
        metric = spec.metrics[0]
        value = filtered[metric.column].agg(AGG_FUNCS[metric.agg])
        name = f"{AGG_LABELS[metric.agg]} de {metric.column}"
        return {**base, "categories": [], "series": [{"name": name, "data": [_number(value)]}]}

    named = {f"m{i}": pd.NamedAgg(column=m.column, aggfunc=AGG_FUNCS[m.agg]) for i, m in enumerate(spec.metrics)}
    grouped = filtered.groupby(_group_key(filtered, spec), dropna=True).agg(**named)

    if spec.chart == "line" or spec.dimension.time_grain:
        grouped = grouped.sort_index()
    else:
        grouped = grouped.sort_values("m0", ascending=False)

    base["truncated"] = len(grouped) > spec.limit
    grouped = grouped.head(spec.limit)
    return {
        **base,
        "categories": [str(label) for label in grouped.index],
        "series": [
            {"name": f"{AGG_LABELS[m.agg]} de {m.column}", "data": [_number(v) for v in grouped[f"m{i}"]]}
            for i, m in enumerate(spec.metrics)
        ],
    }
