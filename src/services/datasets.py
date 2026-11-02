"""Regras de negócio de datasets: upload, exclusão em cascata, perfilamento e amostra.

Os routers em src/routers/api/datasets.py ficam só com a camada HTTP (validação de
entrada via Pydantic, códigos de status) e chamam estas funções para o resto.
"""

import io
import os
import uuid

import pandas as pd
from fastapi import HTTPException, status
from psycopg.types.json import Jsonb

from src.core.logging_config import logger
from src.core.storage import get_minio_client
from src.services.analytics.runtime import dataframe_cache
from src.services.profiling import load_dataframe, profile_dataframe

MAX_UPLOAD_BYTES = 10_000_000  # 10 MB
SAMPLE_ROWS = 20


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


def save_uploaded_dataset(conn, user_id: int, filename: str, content: bytes) -> dict:
    """Valida, armazena no MinIO e registra um dataset novo. Levanta HTTPException em caso de erro."""
    extension = os.path.splitext(filename or "")[1].lower()
    if extension not in ALLOWED_FORMATS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Formato de arquivo não permitido")

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

    dataset = conn.execute(
        """
        INSERT INTO datasets (owner_user_id, original_name, object_key, format, size_bytes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, original_name, format, size_bytes
        """,
        (user_id, filename, object_key, extension, len(content)),
    ).fetchone()

    logger.info(
        "Dataset enviado: id=%s owner_id=%s original_name=%r size_bytes=%s",
        dataset["id"], user_id, filename, len(content),
    )
    return dataset


def delete_dataset_core(conn, dataset_id: int, object_key: str) -> None:
    """Apaga o dataset por completo: arquivo no MinIO + linhas no Postgres. Não comita (quem chama decide quando).

    Usada tanto pelo próprio dono (DELETE /datasets/{id}) quanto pela exclusão
    forçada de um usuário (DELETE /users/{id}?force=true), que apaga os
    datasets de outra pessoa antes de apagar a conta.
    """
    dataframe_cache.evict(object_key)  # libera a memória do arquivo apagado
    try:
        get_minio_client().remove_object(os.environ["MINIO_BUCKET"], object_key)
    except Exception as exc:
        # Não travamos a exclusão por causa do MinIO: preferimos um objeto órfão
        # (que pode ser limpo depois) a deixar o usuário preso para sempre.
        logger.warning("Falha ao remover objeto do MinIO: object_key=%s erro=%s", object_key, exc)

    conn.execute("DELETE FROM dataset_columns WHERE dataset_id = %s", (dataset_id,))
    conn.execute("DELETE FROM dataset_profiles WHERE dataset_id = %s", (dataset_id,))
    conn.execute("DELETE FROM datasets WHERE id = %s", (dataset_id,))


def list_datasets_for_user(conn, user_id: int) -> list[dict]:
    return conn.execute(
        """
        SELECT d.id, d.original_name, d.format, d.size_bytes, d.created_at,
               EXISTS (SELECT 1 FROM dataset_profiles p WHERE p.dataset_id = d.id) AS profiled
        FROM datasets d
        WHERE d.owner_user_id = %s
        ORDER BY d.id DESC
        """,
        (user_id,),
    ).fetchall()


def get_owned_dataset(conn, dataset_id: int, user_id: int) -> dict:
    """Busca um dataset garantindo que pertence ao usuário. 404 (não 403) para não revelar se existe."""
    dataset = conn.execute(
        "SELECT id, object_key, format FROM datasets WHERE id = %s AND owner_user_id = %s",
        (dataset_id, user_id),
    ).fetchone()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset não encontrado")
    return dataset


def create_profile_for_dataset(conn, dataset_id: int, user_id: int, object_key: str, file_format: str) -> dict:
    df = load_dataframe(object_key, file_format)
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

    logger.info(
        "Dataset perfilado: id=%s owner_id=%s row_count=%s colunas=%s",
        dataset_id, user_id, result["row_count"], len(result["columns"]),
    )
    return result


def get_stored_profile(conn, dataset_id: int) -> dict:
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


def get_column_types(conn, dataset_id: int) -> dict[str, str] | None:
    """nome da coluna -> inferred_type, do perfil salvo. None se o dataset ainda não foi perfilado."""
    has_profile = conn.execute(
        "SELECT 1 AS ok FROM dataset_profiles WHERE dataset_id = %s", (dataset_id,)
    ).fetchone()
    if has_profile is None:
        return None
    rows = conn.execute(
        "SELECT column_name, inferred_type FROM dataset_columns WHERE dataset_id = %s", (dataset_id,)
    ).fetchall()
    return {row["column_name"]: row["inferred_type"] for row in rows}


def _cell_to_str(value) -> str | None:
    """None para ausente (NaN/NaT); todo o resto vira texto — é uma amostra visual,
    não um valor que algum código vá reprocessar."""
    if pd.isna(value):
        return None
    return str(value)


def get_dataset_sample(object_key: str, file_format: str) -> dict:
    df = load_dataframe(object_key, file_format)
    sample = df.head(SAMPLE_ROWS)

    return {
        "columns": [str(c) for c in sample.columns],
        "rows": [[_cell_to_str(v) for v in row] for row in sample.itertuples(index=False, name=None)],
        "total_rows": len(df),
        "sample_size": len(sample),
    }
