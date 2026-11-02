import io
import os
import re

import numpy as np
import pandas as pd

from core import storage

HISTOGRAM_BINS = 10

# Mapeia o "kind" do dtype do pandas para um nome amigável.
# Referência: https://numpy.org/doc/stable/reference/generated/numpy.dtype.kind.html
_KIND_TO_TYPE_NAME = {
    "i": "integer",
    "u": "integer",
    "f": "float",
    "b": "boolean",
    "M": "datetime",
    "O": "text",
}


def _friendly_type_name(dtype) -> str:
    return _KIND_TO_TYPE_NAME.get(dtype.kind, "text")


DATETIME_MIN_PARSE_RATE = 0.95
DATETIME_SAMPLE_SIZE = 10_000
# Exige formato de data (com separador) antes de tentar parsear: evita que "12345" ou códigos virem data.
_DATE_SHAPE = re.compile(r"^\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?\s*$")


_YEAR_FIRST = re.compile(r"^\s*\d{4}[-/.]")


def parse_datetimes(series: pd.Series) -> pd.Series:
    """Único ponto de parsing de datas: perfilador e engine de analytics usam esta função.

    Ano na frente (2026-01-10) é sempre ano-mês-dia. Nos demais formatos vale dayfirst=True, porque
    o público é pt-BR ("01/02/2026" = 1º de fevereiro). Aplicar dayfirst a tudo trocaria dia e mês
    das datas ISO sem avisar, então os dois grupos são parseados separadamente."""
    text = series.astype("string")
    year_first = text.str.match(_YEAR_FIRST).fillna(False).astype(bool)
    parts = [
        pd.to_datetime(text[year_first], errors="coerce", format="mixed", dayfirst=False),
        pd.to_datetime(text[~year_first], errors="coerce", format="mixed", dayfirst=True),
    ]
    return pd.concat(parts).reindex(series.index)


def _looks_like_datetime(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(DATETIME_SAMPLE_SIZE)
    if sample.empty or sample.str.match(_DATE_SHAPE).mean() < DATETIME_MIN_PARSE_RATE:
        return False
    return parse_datetimes(sample).notna().mean() >= DATETIME_MIN_PARSE_RATE


def infer_column_type(series: pd.Series) -> str:
    inferred = _friendly_type_name(series.dtype)
    if inferred == "text" and _looks_like_datetime(series):
        return "datetime"
    return inferred


def load_dataframe(object_key: str, extension: str) -> pd.DataFrame:
    client = storage.get_minio_client()
    bucket = os.environ["MINIO_BUCKET"]

    response = client.get_object(bucket, object_key)
    try:
        content = response.read()
    finally:
        response.close()
        response.release_conn()

    buffer = io.BytesIO(content)
    if extension == ".csv":
        return pd.read_csv(buffer)
    if extension == ".xlsx":
        return pd.read_excel(buffer)
    raise ValueError(f"Formato não suportado para perfilamento: {extension}")


def _numeric_stats(series: pd.Series) -> dict | None:
    """Min/máx/média/mediana — só faz sentido para colunas numéricas, e só se sobrar
    algum valor não-nulo (uma coluna inteiramente vazia não tem estatística)."""
    non_null = series.dropna()
    if non_null.empty:
        return None
    return {
        "min": float(non_null.min()),
        "max": float(non_null.max()),
        "mean": float(non_null.mean()),
        "median": float(non_null.median()),
    }


def _histogram(series: pd.Series, bins: int = HISTOGRAM_BINS) -> dict | None:
    """Conta quantos valores caem em cada uma de `bins` faixas iguais entre o mínimo e o máximo.
    Base para o histograma do dashboard. None se não sobrar valor numérico (coluna vazia)."""
    non_null = series.dropna()
    if non_null.empty:
        return None
    counts, edges = np.histogram(non_null, bins=bins)
    return {"bin_edges": [float(e) for e in edges], "counts": [int(c) for c in counts]}


TOP_VALUES_LIMIT = 5


def _top_values(series: pd.Series, limit: int = TOP_VALUES_LIMIT) -> list[dict]:
    """Os `limit` valores mais frequentes de uma coluna de texto, ignorando valores ausentes."""
    counts = series.dropna().astype(str).value_counts().head(limit)
    return [{"value": value, "count": int(count)} for value, count in counts.items()]


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Calcula as estatísticas de perfilamento de um DataFrame já carregado."""
    columns = []
    for column_name in df.columns:
        series = df[column_name]
        inferred_type = infer_column_type(series)
        stats = _numeric_stats(series) if inferred_type in ("integer", "float") else None
        columns.append(
            {
                "column_name": str(column_name),
                "inferred_type": inferred_type,
                "null_count": int(series.isna().sum()),
                "distinct_count": int(series.nunique(dropna=True)),
                "min_value": stats["min"] if stats else None,
                "max_value": stats["max"] if stats else None,
                "mean_value": stats["mean"] if stats else None,
                "median_value": stats["median"] if stats else None,
                "top_values": _top_values(series) if inferred_type == "text" else None,
                "histogram": _histogram(series) if inferred_type in ("integer", "float") else None,
            }
        )

    return {
        "row_count": len(df),
        "duplicate_row_count": int(df.duplicated().sum()),
        "columns": columns,
    }
