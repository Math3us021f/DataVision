"""Regras de negócio de datasets: upload, exclusão em cascata, perfilamento e amostra.

As rotas em datasets/api.py ficam só com a camada HTTP (validação da entrada e códigos de status) e chamam
estas funções para o resto.
"""

import io
import logging
import os
import uuid

import pandas as pd
from django.db import transaction
from django.db.models import Exists, OuterRef
from ninja.errors import HttpError

from analytics.runtime import dataframe_cache
from core import storage
from datasets.models import Dataset, DatasetColumn, DatasetColumnTopValue, DatasetProfile
from datasets.profiling import load_dataframe, profile_dataframe

logger = logging.getLogger("datavision")

MAX_UPLOAD_BYTES = 10_000_000  # 10 MB
SAMPLE_ROWS = 20


def _is_valid_xlsx(content: bytes) -> bool:
    # .xlsx é, por baixo dos panos, um arquivo ZIP — todo ZIP começa com essa assinatura de bytes.
    return content[:4] == b"PK\x03\x04"


def _is_valid_csv(content: bytes) -> bool:
    # Não existe uma "assinatura mágica" para CSV (é texto puro). O melhor que dá para verificar sem interpretar o
    # conteúdo de verdade é: decodifica como texto e não tem bytes nulos (um arquivo binário disfarçado de .csv
    # normalmente falha aqui).
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


def save_uploaded_dataset(user, filename: str, size: int, read_content) -> dict:
    """Valida, armazena no MinIO e registra um dataset novo. Levanta HttpError em caso de erro.

    `size` é o tamanho que o Django já conhece do arquivo recebido e `read_content()` devolve o conteúdo: assim um
    arquivo grande demais é recusado (413) sem nem ser lido para a memória."""
    extension = os.path.splitext(filename or "")[1].lower()
    if extension not in ALLOWED_FORMATS:
        raise HttpError(403, "Formato de arquivo não permitido")

    if size > MAX_UPLOAD_BYTES:
        raise HttpError(413, "Arquivo grande demais")

    content = read_content()
    if not ALLOWED_FORMATS[extension](content):
        raise HttpError(400, "O conteúdo do arquivo não corresponde ao formato declarado pela extensão")

    # Nome de armazenamento gerado pelo servidor — nunca usamos o nome original do arquivo como caminho no MinIO,
    # para não depender de entrada do usuário na hora de montar o object_key.
    object_key = f"{uuid.uuid4().hex}{extension}"
    storage.get_minio_client().put_object(os.environ["MINIO_BUCKET"], object_key, io.BytesIO(content), length=len(content))

    dataset = Dataset.objects.create(owner=user, original_name=filename, object_key=object_key, format=extension, size_bytes=len(content))
    logger.info("Dataset enviado: id=%s owner_id=%s original_name=%r size_bytes=%s", dataset.pk, user.pk, filename, len(content))
    return {"id": dataset.pk, "original_name": dataset.original_name, "format": dataset.format, "size_bytes": dataset.size_bytes}


def delete_dataset(dataset: Dataset) -> None:
    """Apaga o dataset por completo: o arquivo no MinIO e as linhas no banco (o perfil, as colunas, os valores
    frequentes e o dashboard vão junto, em cascata). Usada pelo próprio dono e pela exclusão forçada de um usuário."""
    dataframe_cache.evict(dataset.object_key)  # libera a memória do arquivo apagado
    try:
        storage.get_minio_client().remove_object(os.environ["MINIO_BUCKET"], dataset.object_key)
    except Exception as exc:
        # Não travamos a exclusão por causa do MinIO: preferimos um objeto órfão (que pode ser limpo depois) a deixar a
        # pessoa presa para sempre.
        logger.warning("Falha ao remover objeto do MinIO: object_key=%s erro=%s", dataset.object_key, type(exc).__name__)
    dataset.delete()


def list_datasets_for_user(user) -> list[dict]:
    has_profile = DatasetProfile.objects.filter(dataset=OuterRef("pk"))
    rows = Dataset.objects.filter(owner=user).annotate(profiled=Exists(has_profile)).order_by("-id")
    return [
        {"id": d.pk, "original_name": d.original_name, "format": d.format, "size_bytes": d.size_bytes, "created_at": d.created_at, "profiled": d.profiled}
        for d in rows
    ]


def get_owned_dataset(dataset_id: int, user) -> Dataset:
    """Busca um dataset garantindo que pertence ao usuário. 404 (não 403) para não revelar se existe."""
    dataset = Dataset.objects.filter(pk=dataset_id, owner=user).first()
    if dataset is None:
        raise HttpError(404, "Dataset não encontrado")
    return dataset


def create_profile_for_dataset(dataset: Dataset, user) -> dict:
    df = load_dataframe(dataset.object_key, dataset.format)
    result = profile_dataframe(df)

    with transaction.atomic():
        DatasetProfile.objects.filter(dataset=dataset).delete()
        dataset.columns.all().delete()  # os valores frequentes vão junto, em cascata
        DatasetProfile.objects.create(dataset=dataset, row_count=result["row_count"], duplicate_row_count=result["duplicate_row_count"])

        columns = DatasetColumn.objects.bulk_create(
            [
                DatasetColumn(
                    dataset=dataset,
                    column_name=col["column_name"],
                    inferred_type=col["inferred_type"],
                    null_count=col["null_count"],
                    distinct_count=col["distinct_count"],
                    min_value=col["min_value"],
                    max_value=col["max_value"],
                    mean_value=col["mean_value"],
                    median_value=col["median_value"],
                    histogram=col["histogram"] or None,
                )
                for col in result["columns"]
            ]
        )
        DatasetColumnTopValue.objects.bulk_create(
            [
                DatasetColumnTopValue(column=column, value=top["value"], occurrence_count=top["count"])
                for column, col in zip(columns, result["columns"])
                for top in col["top_values"] or []
            ]
        )

    logger.info("Dataset perfilado: id=%s owner_id=%s row_count=%s colunas=%s", dataset.pk, user.pk, result["row_count"], len(result["columns"]))
    return result


def get_stored_profile(dataset: Dataset) -> dict:
    profile = DatasetProfile.objects.filter(dataset=dataset).first()
    if profile is None:
        raise HttpError(404, "Este dataset ainda não foi perfilado")

    columns = list(dataset.columns.order_by("id").prefetch_related("top_values"))
    return {
        "row_count": profile.row_count,
        "duplicate_row_count": profile.duplicate_row_count,
        "columns": [
            {
                "column_name": c.column_name,
                "inferred_type": c.inferred_type,
                "null_count": c.null_count,
                "distinct_count": c.distinct_count,
                "min_value": c.min_value,
                "max_value": c.max_value,
                "mean_value": c.mean_value,
                "median_value": c.median_value,
                "histogram": c.histogram,
                # Os mais frequentes primeiro (a ordem da inserção desempata, como no FastAPI).
                "top_values": [
                    {"value": t.value, "count": t.occurrence_count}
                    for t in sorted(c.top_values.all(), key=lambda t: (-t.occurrence_count, t.id))
                ]
                or None,
            }
            for c in columns
        ],
    }


def get_column_types(dataset: Dataset) -> dict[str, str] | None:
    """nome da coluna -> inferred_type, do perfil salvo. None se o dataset ainda não foi perfilado."""
    if not DatasetProfile.objects.filter(dataset=dataset).exists():
        return None
    return dict(dataset.columns.values_list("column_name", "inferred_type"))


def _cell_to_str(value) -> str | None:
    """None para ausente (NaN/NaT); todo o resto vira texto — é uma amostra visual, não um valor que algum código vá
    reprocessar."""
    if pd.isna(value):
        return None
    return str(value)


def get_dataset_sample(dataset: Dataset) -> dict:
    df = load_dataframe(dataset.object_key, dataset.format)
    sample = df.head(SAMPLE_ROWS)
    return {
        "columns": [str(c) for c in sample.columns],
        "rows": [[_cell_to_str(v) for v in row] for row in sample.itertuples(index=False, name=None)],
        "total_rows": len(df),
        "sample_size": len(sample),
    }
