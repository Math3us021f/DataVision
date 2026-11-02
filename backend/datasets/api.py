"""Datasets do próprio usuário: enviar, listar, excluir, perfilar e ver uma amostra."""

import logging
from datetime import datetime

from ninja import File, Router, Schema, Status, UploadedFile

from accounts.auth import SessionAuth
from datasets import services

logger = logging.getLogger("datavision")
router = Router(tags=["datasets"])
session_auth = SessionAuth()


class DatasetOut(Schema):
    id: int
    original_name: str
    format: str
    size_bytes: int
    # Só a listagem preenche estes dois; a resposta do upload não os traz.
    created_at: datetime | None = None
    profiled: bool = False


class TopValueOut(Schema):
    value: str
    count: int


class HistogramOut(Schema):
    bin_edges: list[float]
    counts: list[int]


class ColumnProfileOut(Schema):
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


class DatasetProfileOut(Schema):
    row_count: int
    duplicate_row_count: int
    columns: list[ColumnProfileOut]


class DatasetSampleOut(Schema):
    columns: list[str]
    rows: list[list[str | None]]
    total_rows: int
    sample_size: int


# "upload" vem antes das rotas com {dataset_id} (e estas só aceitam números), para nunca serem confundidos.
@router.post("/datasets/upload", auth=session_auth, response={201: DatasetOut}, summary="Envia um arquivo CSV ou Excel")
def upload_dataset(request, file: File[UploadedFile]):
    return Status(201, services.save_uploaded_dataset(request.auth, file.name, file.size, file.read))


@router.get("/datasets", auth=session_auth, response=list[DatasetOut], summary="Meus datasets (mais novos primeiro)")
def list_my_datasets(request):
    return services.list_datasets_for_user(request.auth)


@router.delete("/datasets/{int:dataset_id}", auth=session_auth, response={204: None}, summary="Exclui um dataset")
def delete_dataset(request, dataset_id: int):
    dataset = services.get_owned_dataset(dataset_id, request.auth)
    services.delete_dataset(dataset)
    logger.info("Dataset excluído: id=%s owner_id=%s", dataset_id, request.auth.pk)
    return Status(204, None)


@router.post("/datasets/{int:dataset_id}/profile", auth=session_auth, response=DatasetProfileOut, summary="Calcula (ou recalcula) o perfil")
def create_profile(request, dataset_id: int):
    dataset = services.get_owned_dataset(dataset_id, request.auth)
    return services.create_profile_for_dataset(dataset, request.auth)


@router.get("/datasets/{int:dataset_id}/profile", auth=session_auth, response=DatasetProfileOut, summary="Perfil salvo")
def get_profile(request, dataset_id: int):
    return services.get_stored_profile(services.get_owned_dataset(dataset_id, request.auth))


@router.get("/datasets/{int:dataset_id}/sample", auth=session_auth, response=DatasetSampleOut, summary="Primeiras linhas do arquivo")
def get_sample(request, dataset_id: int):
    return services.get_dataset_sample(services.get_owned_dataset(dataset_id, request.auth))
