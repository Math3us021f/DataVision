"""Testes do endpoint de métricas (Etapa 5)."""

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


def test_admin_ve_metricas(admin_client):
    response = admin_client.get("/metrics/system")
    assert response.status_code == 200
    body = response.json()
    assert "cpu_percent" in body
    assert "memory" in body
    assert "disk" in body
    assert "network" in body
    assert body["memory"]["percent"] >= 0


def test_anonimo_nao_ve_metricas(client):
    response = client.get("/metrics/system")
    assert response.status_code == 401


def test_nao_admin_nao_ve_metricas(admin_client):
    username = f"user_{uuid.uuid4().hex[:8]}"
    admin_client.post("/users", json={"username": username, "password": "senha123"})

    non_admin_client = TestClient(app)
    non_admin_client.post("/login", json={"username": username, "password": "senha123"})

    response = non_admin_client.get("/metrics/system")
    assert response.status_code == 403
