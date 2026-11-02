from fastapi import APIRouter, Depends, UploadFile, status
from pydantic import BaseModel

from src.core.auth import get_current_user
from src.core.db import get_connection
from src.core.logging_config import logger
from src.services.datasets import (
    MAX_UPLOAD_BYTES,
    create_profile_for_dataset,
    delete_dataset_core,
    get_dataset_sample,
    get_owned_dataset,
    get_stored_profile,
    list_datasets_for_user,
    save_uploaded_dataset,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetOut(BaseModel):
    id: int
    original_name: str
    format: str
    size_bytes: int


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=DatasetOut)
async def upload_dataset(file: UploadFile, user: dict = Depends(get_current_user)) -> dict:
    # Lê no máximo 1 byte além do limite: um arquivo gigante é recusado (413) sem ser carregado inteiro na memória.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    with get_connection() as conn:
        dataset = save_uploaded_dataset(conn, user["id"], file.filename, content)
        conn.commit()
    return dataset


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: int, user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        dataset = get_owned_dataset(conn, dataset_id, user["id"])
        delete_dataset_core(conn, dataset_id, dataset["object_key"])
        conn.commit()

    logger.info("Dataset excluído: id=%s owner_id=%s", dataset_id, user["id"])


@router.get("", response_model=list[DatasetOut])
def list_my_datasets(user: dict = Depends(get_current_user)) -> list[dict]:
    with get_connection() as conn:
        return list_datasets_for_user(conn, user["id"])


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
        dataset = get_owned_dataset(conn, dataset_id, user["id"])
        result = create_profile_for_dataset(conn, dataset_id, user["id"], dataset["object_key"], dataset["format"])
        conn.commit()
    return result


@router.get("/{dataset_id}/profile", response_model=DatasetProfileOut)
def get_profile(dataset_id: int, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        get_owned_dataset(conn, dataset_id, user["id"])
        return get_stored_profile(conn, dataset_id)


class DatasetSampleOut(BaseModel):
    columns: list[str]
    rows: list[list[str | None]]
    total_rows: int
    sample_size: int


@router.get("/{dataset_id}/sample", response_model=DatasetSampleOut)
def get_sample(dataset_id: int, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        dataset = get_owned_dataset(conn, dataset_id, user["id"])

    return get_dataset_sample(dataset["object_key"], dataset["format"])
