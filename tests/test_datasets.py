"""Testes de upload/listagem de datasets (Etapa 9). Dependem do Postgres e do MinIO reais."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def logged_client():
    """Usuário comum (não-admin) logado — datasets são por usuário, não exigem admin."""
    username = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})

    with TestClient(app) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


def upload(client, filename: str, content: bytes):
    return client.post("/datasets/upload", files={"file": (filename, io.BytesIO(content), "application/octet-stream")})


def test_upload_csv_valido(logged_client):
    response = upload(logged_client, "dados.csv", b"a,b\n1,2\n")
    assert response.status_code == 201
    body = response.json()
    assert body["original_name"] == "dados.csv"
    assert body["format"] == ".csv"
    assert body["size_bytes"] == 8


def test_upload_xlsx_valido(logged_client):
    # Assinatura real de ZIP (xlsx é um zip por baixo) + conteúdo qualquer.
    conteudo_zip_falso = b"PK\x03\x04" + b"conteudo qualquer de um xlsx minimo"
    response = upload(logged_client, "planilha.xlsx", conteudo_zip_falso)
    assert response.status_code == 201


def test_extensao_nao_permitida_e_rejeitada(logged_client):
    response = upload(logged_client, "script.exe", b"MZ fake binary")
    assert response.status_code == 403


def test_conteudo_nao_bate_com_extensao_e_rejeitado(logged_client):
    # .csv com bytes nulos: não é texto de verdade, não deveria passar.
    response = upload(logged_client, "fake.csv", b"\x00\x01\x02binario")
    assert response.status_code == 400


def test_xlsx_sem_assinatura_zip_e_rejeitado(logged_client):
    response = upload(logged_client, "nao_e_xlsx_de_verdade.xlsx", b"isso aqui nao e um zip")
    assert response.status_code == 400


def test_arquivo_grande_demais_e_rejeitado(logged_client):
    from src.routers.datasets import MAX_UPLOAD_BYTES

    conteudo_grande = b"a" * (MAX_UPLOAD_BYTES + 1)
    response = upload(logged_client, "grande.csv", conteudo_grande)
    assert response.status_code == 413


def test_listagem_mostra_so_os_proprios_datasets(logged_client):
    upload(logged_client, "meu.csv", b"a,b\n1,2\n")

    response = logged_client.get("/datasets")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(d["original_name"] for d in body)


def test_anonimo_nao_pode_fazer_upload(client):
    response = upload(client, "qualquer.csv", b"a,b\n1,2\n")
    assert response.status_code == 401


def test_anonimo_nao_pode_listar(client):
    response = client.get("/datasets")
    assert response.status_code == 401
