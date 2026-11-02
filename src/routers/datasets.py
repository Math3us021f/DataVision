import io
import os
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from src.auth import get_current_user
from src.db import get_connection
from src.logging_config import logger
from src.profiling import load_dataframe, profile_dataframe
from src.storage import get_minio_client

router = APIRouter(prefix="/datasets", tags=["datasets"])

MAX_UPLOAD_BYTES = 10_000_000  # 10 MB


def _is_valid_xlsx(content: bytes) -> bool:
    # .xlsx é, por baixo dos panos, um arquivo ZIP — todo ZIP começa com essa assinatura de bytes.
    return content[:4] == b"PK\x03\x04"


def _is_valid_csv(content: bytes) -> bool:
    # Não existe uma "assinatura mágica" para CSV (é texto puro). O melhor que dá pra verificar
    # sem interpretar o conteúdo de verdade é: decodifica como texto e não tem bytes nulos
    # (um arquivo binário disfarçado de .csv normalmente falha aqui).
    if b"\x00" in content:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


ALLOWED_FORMATS = {
    ".csv": _is_valid_csv,
    ".xlsx": _is_valid_xlsx,
}


class DatasetOut(BaseModel):
    id: int
    original_name: str
    format: str
    size_bytes: int


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=DatasetOut)
async def upload_dataset(file: UploadFile, user: dict = Depends(get_current_user)) -> dict:
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_FORMATS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Formato de arquivo não permitido")

    content = await file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Arquivo grande demais")

    validator = ALLOWED_FORMATS[extension]
    if not validator(content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O conteúdo do arquivo não corresponde ao formato declarado pela extensão",
        )

    # Nome de armazenamento gerado pelo servidor — nunca usamos o nome original do arquivo
    # como caminho no MinIO, para não depender de entrada do usuário na hora de montar o object_key.
    object_key = f"{uuid.uuid4().hex}{extension}"

    client = get_minio_client()
    bucket = os.environ["MINIO_BUCKET"]
    client.put_object(bucket, object_key, io.BytesIO(content), length=len(content))

    with get_connection() as conn:
        dataset = conn.execute(
            """
            INSERT INTO datasets (owner_user_id, original_name, object_key, format, size_bytes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, original_name, format, size_bytes
            """,
            (user["id"], file.filename, object_key, extension, len(content)),
        ).fetchone()
        conn.commit()

    logger.info(
        "Dataset enviado: id=%s owner_id=%s original_name=%r size_bytes=%s",
        dataset["id"], user["id"], file.filename, len(content),
    )
    return dataset


def delete_dataset_core(conn, dataset_id: int, object_key: str) -> None:
    """Apaga o dataset por completo: arquivo no MinIO + linhas no Postgres. Não comita (quem chama decide quando).

    Usada tanto pelo próprio dono (DELETE /datasets/{id}) quanto pela exclusão
    forçada de um usuário (DELETE /users/{id}?force=true), que apaga os
    datasets de outra pessoa antes de apagar a conta.
    """
    try:
        get_minio_client().remove_object(os.environ["MINIO_BUCKET"], object_key)
    except Exception as exc:
        # Não travamos a exclusão por causa do MinIO: preferimos um objeto órfão
        # (que pode ser limpo depois) a deixar o usuário preso para sempre.
        logger.warning("Falha ao remover objeto do MinIO: object_key=%s erro=%s", object_key, exc)

    conn.execute("DELETE FROM dataset_columns WHERE dataset_id = %s", (dataset_id,))
    conn.execute("DELETE FROM dataset_profiles WHERE dataset_id = %s", (dataset_id,))
    conn.execute("DELETE FROM datasets WHERE id = %s", (dataset_id,))


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: int, user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        dataset = _get_owned_dataset(conn, dataset_id, user["id"])
        delete_dataset_core(conn, dataset_id, dataset["object_key"])
        conn.commit()

    logger.info("Dataset excluído: id=%s owner_id=%s", dataset_id, user["id"])


@router.get("", response_model=list[DatasetOut])
def list_my_datasets(user: dict = Depends(get_current_user)) -> list[dict]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, original_name, format, size_bytes
            FROM datasets
            WHERE owner_user_id = %s
            ORDER BY id DESC
            """,
            (user["id"],),
        ).fetchall()


def _get_owned_dataset(conn, dataset_id: int, user_id: int) -> dict:
    """Busca um dataset garantindo que pertence ao usuário. 404 (não 403) para não revelar se existe."""
    dataset = conn.execute(
        "SELECT id, object_key, format FROM datasets WHERE id = %s AND owner_user_id = %s",
        (dataset_id, user_id),
    ).fetchone()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset não encontrado")
    return dataset


class TopValueOut(BaseModel):
    value: str
    count: int


class HistogramOut(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class ColumnProfileOut(BaseModel):
    column_name: str
    inferred_type: str
    null_count: int
    distinct_count: int
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None
    median_value: float | None = None
    top_values: list[TopValueOut] | None = None
    histogram: HistogramOut | None = None


class DatasetProfileOut(BaseModel):
    row_count: int
    duplicate_row_count: int
    columns: list[ColumnProfileOut]


@router.post("/{dataset_id}/profile", response_model=DatasetProfileOut)
def create_profile(dataset_id: int, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        dataset = _get_owned_dataset(conn, dataset_id, user["id"])

        df = load_dataframe(dataset["object_key"], dataset["format"])
        result = profile_dataframe(df)

        conn.execute("DELETE FROM dataset_columns WHERE dataset_id = %s", (dataset_id,))
        conn.execute("DELETE FROM dataset_profiles WHERE dataset_id = %s", (dataset_id,))

        conn.execute(
            """
            INSERT INTO dataset_profiles (dataset_id, row_count, duplicate_row_count)
            VALUES (%s, %s, %s)
            """,
            (dataset_id, result["row_count"], result["duplicate_row_count"]),
        )
        for col in result["columns"]:
            column_row = conn.execute(
                """
                INSERT INTO dataset_columns
                    (dataset_id, column_name, inferred_type, null_count, distinct_count,
                     min_value, max_value, mean_value, median_value, histogram)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    dataset_id, col["column_name"], col["inferred_type"], col["null_count"], col["distinct_count"],
                    col["min_value"], col["max_value"], col["mean_value"], col["median_value"],
                    Jsonb(col["histogram"]) if col["histogram"] else None,
                ),
            ).fetchone()

            for top in col["top_values"] or []:
                conn.execute(
                    "INSERT INTO dataset_column_top_values (dataset_column_id, value, occurrence_count) VALUES (%s, %s, %s)",
                    (column_row["id"], top["value"], top["count"]),
                )
        conn.commit()

    logger.info(
        "Dataset perfilado: id=%s owner_id=%s row_count=%s colunas=%s",
        dataset_id, user["id"], result["row_count"], len(result["columns"]),
    )
    return result


@router.get("/{dataset_id}/profile", response_model=DatasetProfileOut)
def get_profile(dataset_id: int, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        _get_owned_dataset(conn, dataset_id, user["id"])

        profile = conn.execute(
            "SELECT row_count, duplicate_row_count FROM dataset_profiles WHERE dataset_id = %s",
            (dataset_id,),
        ).fetchone()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Este dataset ainda não foi perfilado",
            )

        columns = conn.execute(
            """
            SELECT id, column_name, inferred_type, null_count, distinct_count,
                   min_value, max_value, mean_value, median_value, histogram
            FROM dataset_columns WHERE dataset_id = %s
            ORDER BY id
            """,
            (dataset_id,),
        ).fetchall()

        top_values_by_column: dict[int, list[dict]] = {}
        if columns:
            rows = conn.execute(
                """
                SELECT dataset_column_id, value, occurrence_count
                FROM dataset_column_top_values
                WHERE dataset_column_id = ANY(%s)
                ORDER BY occurrence_count DESC
                """,
                ([c["id"] for c in columns],),
            ).fetchall()
            for row in rows:
                top_values_by_column.setdefault(row["dataset_column_id"], []).append(
                    {"value": row["value"], "count": row["occurrence_count"]}
                )

        for column in columns:
            column["top_values"] = top_values_by_column.get(column.pop("id")) or None

    return {**profile, "columns": columns}


SAMPLE_ROWS = 20


class DatasetSampleOut(BaseModel):
    columns: list[str]
    rows: list[list[str | None]]
    total_rows: int
    sample_size: int


def _cell_to_str(value) -> str | None:
    """None para ausente (NaN/NaT); todo o resto vira texto — é uma amostra visual,
    não um valor que algum código vá reprocessar."""
    if pd.isna(value):
        return None
    return str(value)


@router.get("/{dataset_id}/sample", response_model=DatasetSampleOut)
def get_sample(dataset_id: int, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        dataset = _get_owned_dataset(conn, dataset_id, user["id"])

    df = load_dataframe(dataset["object_key"], dataset["format"])
    sample = df.head(SAMPLE_ROWS)

    return {
        "columns": [str(c) for c in sample.columns],
        "rows": [[_cell_to_str(v) for v in row] for row in sample.itertuples(index=False, name=None)],
        "total_rows": len(df),
        "sample_size": len(sample),
    }
