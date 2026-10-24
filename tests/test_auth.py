"""Testes de autenticação. Dependem do Postgres real (serviço `db` do Docker Compose)."""

import os

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    """Cliente novo a cada teste, para não vazar cookies de sessão entre testes."""
    return TestClient(app)


def test_login_com_credenciais_validas(client):
    response = client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    assert "session" in response.cookies


def test_login_com_senha_invalida(client):
    response = client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada"})
    assert response.status_code == 401


def test_login_com_usuario_inexistente(client):
    response = client.post("/login", json={"username": "nao-existe", "password": "qualquer"})
    assert response.status_code == 401


def test_me_sem_sessao_retorna_401(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_me_com_sessao_valida_retorna_usuario(client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})

    response = client.get("/me")
    assert response.status_code == 200
    assert response.json() == {"username": ADMIN_USERNAME, "is_admin": True}


def test_logout_invalida_a_sessao(client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})

    logout_response = client.post("/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/me")
    assert me_response.status_code == 401
