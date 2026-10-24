"""Testes de perfilamento de datasets (Etapa 10). Confere números exatos, não só 'funcionou'."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

CSV_CONHECIDO = b"nome,idade,cidade\nAna,30,SP\nBruno,25,RJ\nCarla,,SP\nAna,30,SP\n"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def logged_client():
    username = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})

    with TestClient(app) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


def upload(client, filename: str, content: bytes) -> int:
    response = client.post(
        "/datasets/upload", files={"file": (filename, io.BytesIO(content), "application/octet-stream")}
    )
    return response.json()["id"]


def test_perfilamento_calcula_numeros_exatos(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    response = logged_client.post(f"/datasets/{dataset_id}/profile")
    assert response.status_code == 200

    body = response.json()
    assert body["row_count"] == 4
    assert body["duplicate_row_count"] == 1

    por_nome = {c["column_name"]: c for c in body["columns"]}
    assert por_nome["nome"] == {"column_name": "nome", "inferred_type": "text", "null_count": 0, "distinct_count": 3}
    assert por_nome["idade"] == {"column_name": "idade", "inferred_type": "float", "null_count": 1, "distinct_count": 2}
    assert por_nome["cidade"] == {"column_name": "cidade", "inferred_type": "text", "null_count": 0, "distinct_count": 2}


def test_get_profile_retorna_o_que_foi_calculado(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)
    logged_client.post(f"/datasets/{dataset_id}/profile")

    response = logged_client.get(f"/datasets/{dataset_id}/profile")
    assert response.status_code == 200
    assert response.json()["row_count"] == 4


def test_get_profile_antes_de_perfilar_retorna_404(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    response = logged_client.get(f"/datasets/{dataset_id}/profile")
    assert response.status_code == 404


def test_reperfilar_substitui_sem_duplicar(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    logged_client.post(f"/datasets/{dataset_id}/profile")
    segunda = logged_client.post(f"/datasets/{dataset_id}/profile")

    assert segunda.status_code == 200
    assert len(segunda.json()["columns"]) == 3  # não dobrou pra 6


def test_dataset_de_outro_usuario_retorna_404(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    outro_username = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": outro_username, "password": "senha123"})

    with TestClient(app) as outro_client:
        outro_client.post("/login", json={"username": outro_username, "password": "senha123"})
        response = outro_client.post(f"/datasets/{dataset_id}/profile")
        assert response.status_code == 404


def test_dataset_inexistente_retorna_404(logged_client):
    response = logged_client.post("/datasets/999999/profile")
    assert response.status_code == 404


def test_anonimo_nao_pode_perfilar(client):
    response = client.post("/datasets/1/profile")
    assert response.status_code == 401
