"""Sessão com prazo por inatividade (15 min), limite absoluto (8 h) e versão da sessão, com o relógio "andando"."""

import pytest
from django.contrib.auth import get_user_model
from django.db.models import F

from accounts.session_policy import (
    BACKGROUND_REQUEST_HEADER,
    EXPIRED_DETAIL,
    IDLE_DETAIL,
)
from tests.conftest import PASSWORD, ApiClient

User = get_user_model()
pytestmark = pytest.mark.django_db

MIN = 60
BACKGROUND = {"HTTP_X_BACKGROUND_REQUEST": "1"}


@pytest.fixture
def user():
    return User.objects.create_user("maria", PASSWORD)


@pytest.fixture
def logged(user, clock):
    cliente = ApiClient()
    assert cliente.post("/login", json={"username": "maria", "password": PASSWORD}).status_code == 200
    return cliente


def test_o_cabecalho_de_requisicao_automatica_tem_o_nome_combinado_com_o_react():
    assert BACKGROUND_REQUEST_HEADER == "X-Background-Request"


def test_sem_atividade_por_15_minutos_a_sessao_cai(logged, clock):
    clock["t"] += 15 * MIN + 1
    resposta = logged.get("/me")
    assert resposta.status_code == 401 and resposta.json()["detail"] == IDLE_DETAIL


def test_logo_antes_do_prazo_ainda_vale(logged, clock):
    clock["t"] += 15 * MIN - 5
    assert logged.get("/me").status_code == 200


def test_cada_atividade_renova_o_prazo(logged, clock):
    for _ in range(5):  # 5 × 14 min = 70 min no total, sempre com atividade antes dos 15 min
        clock["t"] += 14 * MIN
        assert logged.get("/me").status_code == 200
    clock["t"] += 15 * MIN + 1
    assert logged.get("/me").status_code == 401


def test_requisicao_automatica_nao_renova_a_sessao(logged, clock):
    clock["t"] += 10 * MIN
    assert logged.get("/me", **BACKGROUND).status_code == 200  # ainda vale e não conta como atividade
    clock["t"] += 6 * MIN  # 16 min desde a última atividade real
    assert logged.get("/me", **BACKGROUND).status_code == 401
    assert logged.get("/me").status_code == 401


def test_requisicao_automatica_nao_reenvia_o_cookie_e_a_da_pessoa_sim(logged, clock):
    clock["t"] += 1 * MIN
    assert "session" not in logged.get("/me", **BACKGROUND).cookies  # a sessão não foi tocada
    assert "session" in logged.get("/me").cookies  # a da pessoa renova e reenvia o cookie


def test_limite_absoluto_de_8_horas_mesmo_com_atividade(logged, clock):
    resposta = None
    for _ in range(49):  # atividade a cada 10 min por 8h10
        clock["t"] += 10 * MIN
        resposta = logged.get("/me")
        if resposta.status_code == 401:
            break
    assert resposta.status_code == 401 and resposta.json()["detail"] == EXPIRED_DETAIL


def test_depois_de_cair_o_cookie_velho_nao_volta_a_valer(logged, clock):
    clock["t"] += 16 * MIN
    assert logged.get("/me").status_code == 401
    clock["t"] -= 16 * MIN  # mesmo "voltando no tempo", a sessão já foi apagada
    assert logged.get("/me").status_code == 401


def test_sessao_sem_as_anotacoes_do_login_e_inicializada(user, clock):
    cliente = ApiClient()
    cliente.force_login(user)  # criada por fora do nosso login: sem start/act/v
    assert cliente.get("/me").status_code == 200
    clock["t"] += 16 * MIN
    assert cliente.get("/me").status_code == 401  # a partir da primeira vez, vale a política


def test_senha_trocada_ou_outras_sessoes_encerradas_derrubam_o_cookie_antigo(logged, user):
    User.objects.filter(pk=user.pk).update(session_version=F("session_version") + 1)
    resposta = logged.get("/me")
    assert resposta.status_code == 401 and resposta.json()["detail"] == "Sessão encerrada"


def test_conta_desativada_perde_a_sessao_na_hora(logged, user):
    User.objects.filter(pk=user.pk).update(is_active=False)
    assert logged.get("/me").status_code == 401


def test_paginas_com_sessao_inativa_vao_para_o_login(logged, clock):
    clock["t"] += 16 * MIN
    for caminho in ("/app", "/app/admin/users"):
        resposta = logged.get(caminho)
        assert resposta.status_code == 302 and resposta["Location"] == "/login", caminho


def test_paginas_nao_renovam_a_sessao(logged, clock):
    clock["t"] += 10 * MIN
    logged.get("/app")  # só carregar a página não conta; a API que ela chama em seguida é que renova
    clock["t"] += 6 * MIN
    assert logged.get("/me").status_code == 401


def test_depois_de_cair_e_possivel_entrar_de_novo(logged, clock):
    clock["t"] += 16 * MIN
    assert logged.get("/me").status_code == 401
    assert logged.post("/login", json={"username": "maria", "password": PASSWORD}).status_code == 200
    assert logged.get("/me").status_code == 200


def test_cookie_adulterado_e_invalido(client):
    client.cookies["session"] = "valor-qualquer-que-nao-existe"
    resposta = client.get("/me")
    assert resposta.status_code == 401 and resposta.json()["detail"] == "Não autenticado"


def test_a_inatividade_e_de_cada_cookie(logged, clock):
    User.objects.create_user("outro", PASSWORD)
    outro = ApiClient()
    outro.post("/login", json={"username": "outro", "password": PASSWORD})
    clock["t"] += 10 * MIN
    assert outro.get("/me").status_code == 200  # só o outro usuário ficou ativo
    clock["t"] += 10 * MIN
    assert outro.get("/me").status_code == 200
    assert logged.get("/me").status_code == 401  # quem passou 20 min parado caiu


def test_prazo_vem_das_configuracoes(logged, settings):
    assert logged.get("/me").json()["idle_timeout_seconds"] == settings.SESSION_IDLE_TIMEOUT_SECONDS == 15 * MIN
