"""Testes das rotas de página: casca da interface (React), tela de login e redirecionamentos de endereços antigos."""

import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

INTERFACE_GERADA = Path("src/static/app/index.html").is_file()


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


def assert_casca_da_interface(response):
    """A casca é o mesmo HTML para qualquer rota da interface; sem build, o servidor avisa com 503."""
    if INTERFACE_GERADA:
        assert response.status_code == 200
        assert '<div id="root">' in response.text and "/static/app/assets/" in response.text
    else:
        assert response.status_code == 503


def assert_redireciona(response, destino):
    assert response.status_code in (302, 307)
    assert response.headers["location"] == destino


def test_login_page_entrega_a_casca_para_anonimo(client):
    assert_casca_da_interface(client.get("/login"))


def test_login_page_com_sessao_redireciona_para_a_interface(admin_client):
    assert_redireciona(admin_client.get("/login"), "/app")


def test_home_sem_sessao_redireciona_para_login(client):
    assert_redireciona(client.get("/"), "/login")


def test_home_com_sessao_redireciona_para_a_interface(admin_client):
    assert_redireciona(admin_client.get("/"), "/app")


def test_interface_sem_sessao_redireciona_para_login(client):
    for path in ("/app", "/app/qualquer/coisa", "/app/admin/users"):
        assert_redireciona(client.get(path), "/login")


def test_interface_com_sessao_entrega_a_casca(non_admin_client):
    for path in ("/app", "/app/qualquer/coisa"):  # o roteamento interno é do navegador
        assert_casca_da_interface(non_admin_client.get(path))


def test_arquivos_da_interface_antiga_nao_existem_mais(client):
    for path in ("/static/css/style.css", "/static/js/api.js", "/static/js/admin_users.js", "/static/vendor/echarts/echarts.min.js"):
        assert client.get(path).status_code == 404


ENDERECOS_ANTIGOS = [
    ("/meus-datasets", "/app/datasets"),
    ("/meus-datasets/42/dashboard", "/app/datasets/42/dashboard"),
    ("/account", "/app/account"),
]


@pytest.mark.parametrize("antigo, novo", ENDERECOS_ANTIGOS)
def test_enderecos_antigos_levam_para_a_interface_nova(non_admin_client, antigo, novo):
    assert_redireciona(non_admin_client.get(antigo), novo)


@pytest.mark.parametrize("antigo, novo", ENDERECOS_ANTIGOS)
def test_enderecos_antigos_sem_sessao_vao_para_o_login(client, antigo, novo):
    assert_redireciona(client.get(antigo), "/login")


PAGINAS_ADMIN = ["users", "metrics", "logs", "files", "audit"]


@pytest.mark.parametrize("pagina", PAGINAS_ADMIN)
def test_pagina_admin_antiga_leva_o_admin_para_a_interface_nova(admin_client, pagina):
    assert_redireciona(admin_client.get(f"/admin/{pagina}"), f"/app/admin/{pagina}")


@pytest.mark.parametrize("pagina", PAGINAS_ADMIN)
def test_pagina_admin_antiga_para_nao_admin_vai_para_o_inicio(non_admin_client, pagina):
    assert_redireciona(non_admin_client.get(f"/admin/{pagina}"), "/app")


@pytest.mark.parametrize("pagina", PAGINAS_ADMIN)
def test_pagina_admin_antiga_sem_sessao_vai_para_o_login(client, pagina):
    assert_redireciona(client.get(f"/admin/{pagina}"), "/login")


def test_pagina_admin_inexistente_da_404(admin_client):
    assert admin_client.get("/admin/nao-existe").status_code == 404


def test_admin_index_leva_para_usuarios(admin_client):
    assert_redireciona(admin_client.get("/admin"), "/app/admin/users")


def test_admin_index_sem_sessao_vai_para_o_login(client):
    assert_redireciona(client.get("/admin"), "/login")


def test_admin_index_para_nao_admin_vai_para_o_inicio(non_admin_client):
    assert_redireciona(non_admin_client.get("/admin"), "/app")
