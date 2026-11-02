"""Painel da home: números exatos e separação de dados por perfil."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def admin_client():
    with TestClient(app) as c:
        c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        yield c


@pytest.fixture
def user_client(admin_client):
    username = f"dash_{uuid.uuid4().hex[:8]}"
    admin_client.post("/users", json={"username": username, "password": "senha-123-x"})
    client = TestClient(app)
    client.post("/login", json={"username": username, "password": "senha-123-x"})
    return client


def upload(client, name="dados.csv", content=b"a,b\n1,2\n"):
    response = client.post("/datasets/upload", files={"file": (name, io.BytesIO(content), "text/csv")})
    return response.json()["id"]


def test_usuario_novo_tem_painel_zerado(user_client):
    body = user_client.get("/dashboard/summary").json()
    assert body["mine"] == {"datasets": 0, "storage_bytes": 0, "profiled": 0}
    assert body["recent_datasets"] == []


def test_numeros_refletem_os_proprios_datasets(user_client):
    dataset_id = upload(user_client)
    upload(user_client, "outro.csv", b"x\n1\n")
    user_client.post(f"/datasets/{dataset_id}/profile")

    body = user_client.get("/dashboard/summary").json()
    assert body["mine"] == {"datasets": 2, "storage_bytes": 12, "profiled": 1}
    assert body["recent_datasets"][0]["original_name"] == "outro.csv"


def test_usuario_nao_ve_datasets_de_outros(admin_client, user_client):
    upload(admin_client, "do_admin.csv")
    body = user_client.get("/dashboard/summary").json()
    assert body["mine"]["datasets"] == 0
    assert body["recent_datasets"] == []


def test_usuario_comum_nao_recebe_dados_de_admin(user_client):
    assert "admin" not in user_client.get("/dashboard/summary").json()


def test_admin_recebe_resumo_do_sistema(admin_client):
    admin = admin_client.get("/dashboard/summary").json()["admin"]
    assert admin["users"]["total"] == admin["users"]["active"] + admin["users"]["inactive"]
    assert admin["recent_audit"]
    assert "password_hash" not in str(admin)


def test_anonimo_recebe_401():
    with TestClient(app) as anon:
        assert anon.get("/dashboard/summary").status_code == 401


def test_home_do_usuario_comum_nao_tem_cartoes_de_admin(user_client):
    html = user_client.get("/").text
    assert 'id="stat-datasets"' in html
    assert 'id="stat-users"' not in html
    assert 'id="recent-audit"' not in html
