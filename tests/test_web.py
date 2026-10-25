"""Testes das páginas HTML (frontend: login, home e módulo administrador)."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def admin_client(client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    return client


@pytest.fixture
def non_admin_client(admin_client):
    username = f"user_{uuid.uuid4().hex[:8]}"
    admin_client.post("/users", json={"username": username, "password": "senha123"})
    with TestClient(app, follow_redirects=False) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


def test_login_page_renderiza_para_anonimo(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Entrar" in response.text


def test_home_sem_sessao_redireciona_para_login(client):
    response = client.get("/")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


def test_login_page_com_sessao_redireciona_para_home(client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})

    response = client.get("/login")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_home_com_sessao_mostra_usuario(client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})

    response = client.get("/")
    assert response.status_code == 200
    assert ADMIN_USERNAME in response.text


def test_static_css_e_servido(client):
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_home_mostra_links_admin_so_para_admin(admin_client, non_admin_client):
    assert 'href="/admin/users"' in admin_client.get("/").text
    assert 'href="/admin/users"' not in non_admin_client.get("/").text


def test_admin_users_sem_sessao_redireciona_para_login(client):
    response = client.get("/admin/users")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


def test_admin_users_para_nao_admin_redireciona_para_home(non_admin_client):
    response = non_admin_client.get("/admin/users")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_admin_users_para_admin_renderiza(admin_client):
    response = admin_client.get("/admin/users")
    assert response.status_code == 200
    assert "Usuários cadastrados" in response.text


def test_admin_metrics_para_admin_renderiza(admin_client):
    response = admin_client.get("/admin/metrics")
    assert response.status_code == 200
    assert "Métricas do sistema" in response.text


def test_admin_metrics_para_nao_admin_redireciona_para_home(non_admin_client):
    response = non_admin_client.get("/admin/metrics")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_admin_metrics_sem_sessao_redireciona_para_login(client):
    response = client.get("/admin/metrics")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


def test_admin_logs_para_admin_renderiza(admin_client):
    response = admin_client.get("/admin/logs")
    assert response.status_code == 200
    assert "Logs da aplicação" in response.text


def test_admin_logs_para_nao_admin_redireciona_para_home(non_admin_client):
    response = non_admin_client.get("/admin/logs")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_admin_logs_sem_sessao_redireciona_para_login(client):
    response = client.get("/admin/logs")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


def test_admin_files_para_admin_renderiza(admin_client):
    response = admin_client.get("/admin/files")
    assert response.status_code == 200
    assert "Explorador de arquivos" in response.text


def test_admin_files_para_nao_admin_redireciona_para_home(non_admin_client):
    response = non_admin_client.get("/admin/files")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


def test_admin_files_sem_sessao_redireciona_para_login(client):
    response = client.get("/admin/files")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


def test_admin_index_redireciona_para_usuarios(admin_client):
    response = admin_client.get("/admin")
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/admin/users"
