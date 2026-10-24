"""Testes do endpoint de logs da aplicação (Etapa 6)."""

import os

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
def admin_client():
    with TestClient(app) as c:
        c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        yield c


def test_admin_le_logs(admin_client):
    response = admin_client.get("/logs/app")
    assert response.status_code == 200
    assert "lines" in response.json()


def test_login_falho_aparece_no_log(client, admin_client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada-de-proposito"})

    logs = admin_client.get("/logs/app", params={"limit": 20}).json()["lines"]
    assert any("Login falhou" in line for line in logs)


def test_anonimo_nao_le_logs(client):
    response = client.get("/logs/app")
    assert response.status_code == 401


def test_limit_e_respeitado(admin_client):
    response = admin_client.get("/logs/app", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()["lines"]) <= 2
