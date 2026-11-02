"""Testes da página de auditoria (Etapa 4 do plano de interface): busca, filtro e paginação."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_client():
    c = TestClient(app)
    c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    return c


def unique_username() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


def test_anonimo_nao_pode_ver_auditoria(client):
    response = client.get("/audit-logs")
    assert response.status_code == 401


def test_nao_admin_nao_pode_ver_auditoria(admin_client):
    username = unique_username()
    admin_client.post("/users", json={"username": username, "password": "senha123"})

    non_admin_client = TestClient(app)
    non_admin_client.post("/login", json={"username": username, "password": "senha123"})

    response = non_admin_client.get("/audit-logs")
    assert response.status_code == 403


def test_criar_usuario_fica_na_auditoria(admin_client):
    username = unique_username()
    admin_client.post("/users", json={"username": username, "password": "senha123"})

    body = admin_client.get("/audit-logs", params={"search": username}).json()
    assert body["total"] == 1
    entry = body["items"][0]
    assert entry["action"] == "create_user"
    assert entry["actor_username"] == ADMIN_USERNAME
    assert entry["target_username"] == username


def test_busca_encontra_tanto_quem_fez_quanto_o_alvo(admin_client):
    username = unique_username()
    created = admin_client.post("/users", json={"username": username, "password": "senha123"}).json()
    admin_client.patch(f"/users/{created['id']}", json={"is_active": False})

    body = admin_client.get("/audit-logs", params={"search": ADMIN_USERNAME}).json()
    assert body["total"] >= 1  # o admin aparece como "quem fez" em várias ações


def test_filtro_por_acao(admin_client):
    username = unique_username()
    created = admin_client.post("/users", json={"username": username, "password": "senha123"}).json()
    admin_client.patch(f"/users/{created['id']}", json={"is_active": False})

    body = admin_client.get(
        "/audit-logs", params={"search": username, "action": "deactivate_user"}
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "deactivate_user"


def test_paginacao_respeita_page_size(admin_client):
    marker = uuid.uuid4().hex[:6]
    for _ in range(5):
        admin_client.post("/users", json={"username": f"aud{marker}_{uuid.uuid4().hex[:4]}", "password": "senha-123-x"})

    page1 = admin_client.get("/audit-logs", params={"search": marker, "page_size": 2, "page": 1}).json()
    page3 = admin_client.get("/audit-logs", params={"search": marker, "page_size": 2, "page": 3}).json()

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page3["items"]) == 1
    assert {i["id"] for i in page1["items"]}.isdisjoint({i["id"] for i in page3["items"]})


def test_lista_de_acoes_conhecidas(admin_client):
    response = admin_client.get("/audit-logs/actions")
    assert response.status_code == 200
    assert "create_user" in response.json()


def test_anonimo_nao_ve_lista_de_acoes(client):
    response = client.get("/audit-logs/actions")
    assert response.status_code == 401
