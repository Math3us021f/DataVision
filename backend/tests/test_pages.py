"""Rotas de página: a casca da interface (React), a tela de login e os endereços antigos que redirecionam."""

import pytest

from core.views import ADMIN_PAGES
from tests.conftest import ApiClient, logged_client, make_user

pytestmark = pytest.mark.django_db


def assert_redireciona(resposta, destino):
    assert resposta.status_code == 302 and resposta["Location"] == destino


@pytest.fixture
def com_build(settings, tmp_path):
    index = tmp_path / "index.html"
    index.write_text('<!doctype html><div id="root"></div><script src="/static/app/assets/x.js"></script>', encoding="utf-8")
    settings.REACT_INDEX = index


def test_login_entrega_a_casca_para_anonimo_e_define_o_cookie_csrf(com_build):
    cliente = ApiClient()
    resposta = cliente.get("/login")
    assert resposta.status_code == 200 and b'<div id="root">' in b"".join(resposta.streaming_content)
    assert "csrftoken" in resposta.cookies  # o React lê este cookie e o devolve em X-CSRFToken


def test_login_com_sessao_vai_para_o_app(common_client):
    assert_redireciona(common_client.get("/login"), "/app")


@pytest.mark.parametrize("caminho", ["/app", "/app/qualquer/coisa", "/app/admin/users", "/app/datasets/7/dashboard"])
def test_interface_sem_sessao_vai_para_o_login(caminho):
    assert_redireciona(ApiClient().get(caminho), "/login")


def test_interface_com_sessao_entrega_a_casca_e_o_cookie_csrf(common_client, com_build):
    for caminho in ("/app", "/app/qualquer/coisa"):  # o roteamento interno é do navegador
        resposta = common_client.get(caminho)
        assert resposta.status_code == 200 and b'<div id="root">' in b"".join(resposta.streaming_content)
        assert "csrftoken" in resposta.cookies


def test_sem_build_o_servidor_avisa_com_503(common_client, settings, tmp_path):
    settings.REACT_INDEX = tmp_path / "nao-existe.html"
    resposta = common_client.get("/app")
    assert resposta.status_code == 503 and "docker compose --profile frontend" in resposta.content.decode()


ENDERECOS_ANTIGOS = [
    ("/", "/app"),
    ("/meus-datasets", "/app/datasets"),
    ("/meus-datasets/42/dashboard", "/app/datasets/42/dashboard"),
    ("/account", "/app/account"),
]


@pytest.mark.parametrize("antigo, novo", ENDERECOS_ANTIGOS)
def test_enderecos_antigos_levam_para_a_interface_nova(common_client, antigo, novo):
    assert_redireciona(common_client.get(antigo), novo)


@pytest.mark.parametrize("antigo, novo", ENDERECOS_ANTIGOS)
def test_enderecos_antigos_sem_sessao_vao_para_o_login(antigo, novo):
    assert_redireciona(ApiClient().get(antigo), "/login")


@pytest.mark.parametrize("pagina", sorted(ADMIN_PAGES))
def test_pagina_admin_antiga_redireciona_conforme_quem_pede(admin_client, common_client, pagina):
    assert_redireciona(admin_client.get(f"/admin/{pagina}"), f"/app/admin/{pagina}")
    assert_redireciona(common_client.get(f"/admin/{pagina}"), "/app")
    assert_redireciona(ApiClient().get(f"/admin/{pagina}"), "/login")


def test_admin_index_e_pagina_inexistente(admin_client, common_client):
    assert_redireciona(admin_client.get("/admin"), "/app/admin/users")
    assert_redireciona(common_client.get("/admin"), "/app")
    assert_redireciona(ApiClient().get("/admin"), "/login")
    assert admin_client.get("/admin/nao-existe").status_code == 404


def test_arquivos_da_interface_antiga_nao_existem_mais():
    cliente = ApiClient()
    for caminho in ("/static/css/style.css", "/static/js/api.js", "/static/js/admin_users.js", "/static/vendor/echarts/echarts.min.js"):
        assert cliente.get(caminho).status_code == 404
