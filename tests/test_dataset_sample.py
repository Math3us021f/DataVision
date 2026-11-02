"""Amostra dos dados reais (GET /datasets/{id}/sample) — 3ª melhoria do perfilamento."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def logged_client():
    username = f"sample_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})
    with TestClient(app) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


def upload(client, filename: str, content: bytes) -> int:
    response = client.post("/datasets/upload", files={"file": (filename, io.BytesIO(content), "text/csv")})
    return response.json()["id"]


def test_amostra_devolve_linhas_e_colunas_exatas(logged_client):
    csv = b"nome,idade\nAna,30\nBruno,25\n"
    dataset_id = upload(logged_client, "amostra.csv", csv)

    response = logged_client.get(f"/datasets/{dataset_id}/sample")
    assert response.status_code == 200
    body = response.json()

    assert body["columns"] == ["nome", "idade"]
    assert body["rows"] == [["Ana", "30"], ["Bruno", "25"]]
    assert body["total_rows"] == 2
    assert body["sample_size"] == 2


def test_amostra_mostra_valor_ausente_como_nulo(logged_client):
    csv = b"nome,idade\nAna,30\nBruno,\n"
    dataset_id = upload(logged_client, "ausente.csv", csv)

    body = logged_client.get(f"/datasets/{dataset_id}/sample").json()
    assert body["rows"][1] == ["Bruno", None]


def test_amostra_limita_a_20_linhas_mas_total_rows_e_real(logged_client):
    linhas = "\n".join(f"item{i}" for i in range(30))
    csv = f"categoria\n{linhas}\n".encode()
    dataset_id = upload(logged_client, "muitas_linhas.csv", csv)

    body = logged_client.get(f"/datasets/{dataset_id}/sample").json()
    assert body["sample_size"] == 20
    assert len(body["rows"]) == 20
    assert body["total_rows"] == 30
    assert body["rows"][0] == ["item0"]


def test_amostra_nao_exige_perfilamento_previo(logged_client):
    dataset_id = upload(logged_client, "sem_perfil.csv", b"a,b\n1,2\n")
    response = logged_client.get(f"/datasets/{dataset_id}/sample")
    assert response.status_code == 200


def test_amostra_de_dataset_de_outro_e_404(logged_client):
    other_id = upload(logged_client, "meu.csv", b"a\n1\n")

    username2 = f"sample2_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username2, "password": "senha123"})
    other_client = TestClient(app)
    other_client.post("/login", json={"username": username2, "password": "senha123"})

    response = other_client.get(f"/datasets/{other_id}/sample")
    assert response.status_code == 404


def test_amostra_sem_login_e_401():
    with TestClient(app) as anon:
        assert anon.get("/datasets/1/sample").status_code == 401
