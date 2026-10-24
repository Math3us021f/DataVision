"""Testes do rate limiting no /login (Etapa 8 — estabilização)."""

import os

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.rate_limit import _failed_attempts

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    _failed_attempts.clear()  # garante que testes anteriores não deixaram bloqueio pendente
    with TestClient(app) as c:
        yield c


def test_apos_5_tentativas_erradas_bloqueia_mesmo_com_senha_certa(client):
    for _ in range(5):
        response = client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada"})
        assert response.status_code == 401

    response = client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert response.status_code == 429


def test_tentativas_abaixo_do_limite_nao_bloqueiam(client):
    for _ in range(4):
        client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada"})

    response = client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert response.status_code == 200


def test_login_bem_sucedido_reseta_o_contador(client):
    for _ in range(4):
        client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada"})

    sucesso = client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert sucesso.status_code == 200

    # depois de um login certo, o contador zera — mais 4 tentativas erradas não deveriam bloquear ainda
    for _ in range(4):
        client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada"})

    response = client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert response.status_code == 200


def test_bloqueio_e_por_usuario_nao_afeta_outros(client):
    for _ in range(5):
        client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada"})

    # outro username não deveria estar bloqueado
    response = client.post("/login", json={"username": "usuario-que-nao-existe", "password": "qualquer"})
    assert response.status_code == 401  # bloqueado por credenciais inválidas, não por rate limit
