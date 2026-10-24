import io
import os

import pandas as pd

from src.storage import get_minio_client

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


def load_dataframe(object_key: str, extension: str) -> pd.DataFrame:
    client = get_minio_client()
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


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Calcula as estatísticas de perfilamento de um DataFrame já carregado."""
    columns = []
    for column_name in df.columns:
        series = df[column_name]
        columns.append(
            {
                "column_name": str(column_name),
                "inferred_type": _friendly_type_name(series.dtype),
                "null_count": int(series.isna().sum()),
                "distinct_count": int(series.nunique(dropna=True)),
            }
        )

    return {
        "row_count": len(df),
        "duplicate_row_count": int(df.duplicated().sum()),
        "columns": columns,
    }
