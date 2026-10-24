"""Testes de gestão de usuários (Etapa 4). Dependem do Postgres real."""

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


def test_admin_cria_usuario(admin_client):
    response = admin_client.post("/users", json={"username": unique_username(), "password": "senha123"})
    assert response.status_code == 201
    body = response.json()
    assert body["is_admin"] is False
    assert body["is_active"] is True


def test_criar_usuario_duplicado_retorna_409(admin_client):
    username = unique_username()
    admin_client.post("/users", json={"username": username, "password": "senha123"})

    response = admin_client.post("/users", json={"username": username, "password": "outrasenha"})
    assert response.status_code == 409


def test_nao_admin_nao_pode_criar_usuario(admin_client):
    username = unique_username()
    admin_client.post("/users", json={"username": username, "password": "senha123"})

    non_admin_client = TestClient(app)
    non_admin_client.post("/login", json={"username": username, "password": "senha123"})

    response = non_admin_client.post("/users", json={"username": unique_username(), "password": "x"})
    assert response.status_code == 403


def test_anonimo_nao_pode_criar_usuario(client):
    response = client.post("/users", json={"username": unique_username(), "password": "x"})
    assert response.status_code == 401


def test_admin_lista_usuarios(admin_client):
    response = admin_client.get("/users")
    assert response.status_code == 200
    assert any(u["username"] == ADMIN_USERNAME for u in response.json())


def test_desativar_usuario_impede_login(admin_client):
    username = unique_username()
    created = admin_client.post("/users", json={"username": username, "password": "senha123"}).json()

    deactivate_response = admin_client.patch(f"/users/{created['id']}", json={"is_active": False})
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    login_response = TestClient(app).post("/login", json={"username": username, "password": "senha123"})
    assert login_response.status_code == 401


def test_admin_nao_pode_desativar_a_propria_conta(admin_client):
    me = admin_client.get("/me").json()
    admin_user = admin_client.get("/users").json()
    admin_id = next(u["id"] for u in admin_user if u["username"] == me["username"])

    response = admin_client.patch(f"/users/{admin_id}", json={"is_active": False})
    assert response.status_code == 400
