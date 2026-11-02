"""Endurecimentos da Etapa 12: cabeçalhos, cookie Secure, timing do login, senha longa, docs em produção, upload gigante."""

import io
import os
import subprocess
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from src.main import app
from src.services.datasets import MAX_UPLOAD_BYTES

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", ["/health", "/login", "/static/css/style.css"])
def test_cabecalhos_de_seguranca_em_todas_as_respostas(client, path):
    headers = client.get(path).headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "same-origin"


def test_cookie_de_sessao_sem_secure_por_padrao_e_com_secure_quando_ligado(client, monkeypatch):
    creds = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}

    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    cookie = client.post("/login", json=creds).headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie.replace("samesite", "")

    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    cookie = client.post("/login", json=creds).headers["set-cookie"].lower()
    assert "; secure" in cookie


def test_login_de_usuario_inexistente_gasta_a_mesma_verificacao_de_senha(client, monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "burn_password_check", lambda password: calls.append(password))

    response = client.post("/login", json={"username": f"nao_existe_{uuid.uuid4().hex[:8]}", "password": "qualquer-senha"})
    assert response.status_code == 401
    assert calls == ["qualquer-senha"]


def test_login_com_senha_gigante_retorna_401_e_nao_500(client):
    for username in (ADMIN_USERNAME, f"nao_existe_{uuid.uuid4().hex[:8]}"):
        response = client.post("/login", json={"username": username, "password": "x" * 500})
        assert response.status_code == 401


def test_docs_somem_em_producao():
    code = "from src.main import app; print(app.docs_url, app.redoc_url, app.openapi_url)"
    run = lambda env: subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, **env}, check=True
    ).stdout.split()

    assert run({"APP_ENV": "production"}) == ["None", "None", "None"]
    assert run({"APP_ENV": "development"}) == ["/docs", "/redoc", "/openapi.json"]


def test_upload_muito_maior_que_o_limite_e_recusado_com_413(client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    gigante = b"a,b\n" + b"1,2\n" * (MAX_UPLOAD_BYTES // 2)  # ~2,5x o limite
    response = client.post("/datasets/upload", files={"file": ("grande.csv", io.BytesIO(gigante), "text/csv")})
    assert response.status_code == 413
