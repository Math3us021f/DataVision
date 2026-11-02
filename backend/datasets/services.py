"""Regras de negócio dos datasets (por enquanto só a exclusão; upload e perfilamento chegam na etapa 7)."""

import logging
import os

from datasets.models import Dataset

logger = logging.getLogger("datavision")


def delete_dataset(dataset: Dataset) -> None:
    """Apaga o dataset por completo: o arquivo no MinIO e as linhas no banco (o perfil, as colunas e o dashboard
    vão junto, em cascata). Usada pelo próprio dono e pela exclusão forçada de um usuário."""
    from core.storage import get_minio_client

    try:
        get_minio_client().remove_object(os.environ["MINIO_BUCKET"], dataset.object_key)
    except Exception as exc:
        # Não travamos a exclusão por causa do MinIO: preferimos um objeto órfão (que pode ser limpo depois) a
        # deixar a pessoa presa para sempre.
        logger.warning("Falha ao remover objeto do MinIO: object_key=%s erro=%s", dataset.object_key, type(exc).__name__)
    dataset.delete()
