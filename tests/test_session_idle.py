"""Sessão com prazo por inatividade (15 min) e limite absoluto (8 h), com o relógio "andando" nos testes."""

import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from src.core import auth
from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

MIN = 60
BACKGROUND = {auth.BACKGROUND_REQUEST_HEADER: "1"}


@pytest.fixture
def clock(monkeypatch):
    state = {"t": time.time()}
    monkeypatch.setattr(auth, "_now", lambda: state["t"])
    return state


@pytest.fixture
def client(clock):
    with TestClient(app, follow_redirects=False) as c:
        assert c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).status_code == 200
        yield c


def test_me_informa_o_prazo_de_inatividade(client):
    assert client.get("/me").json()["idle_timeout_seconds"] == 15 * MIN


def test_sem_atividade_por_15_minutos_a_sessao_cai(client, clock):
    clock["t"] += 15 * MIN + 1
    resposta = client.get("/me")
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == auth.IDLE_DETAIL


def test_logo_antes_do_prazo_ainda_vale(client, clock):
    clock["t"] += 15 * MIN - 5
    assert client.get("/me").status_code == 200


def test_cada_atividade_renova_o_prazo(client, clock):
    for _ in range(5):  # 5 × 14 min = 70 min no total, sempre com atividade antes dos 15 min
        clock["t"] += 14 * MIN
        assert client.get("/me").status_code == 200
    clock["t"] += 15 * MIN + 1
    assert client.get("/me").status_code == 401


def test_requisicao_automatica_nao_renova_a_sessao(client, clock):
    clock["t"] += 10 * MIN
    resposta = client.get("/me", headers=BACKGROUND)
    assert resposta.status_code == 200
    assert "set-cookie" not in resposta.headers  # não reassinou o cookie

    clock["t"] += 6 * MIN  # 16 min desde a última atividade real
    assert client.get("/me", headers=BACKGROUND).status_code == 401
    assert client.get("/me").status_code == 401


def test_requisicao_da_pessoa_reassina_o_cookie(client, clock):
    clock["t"] += 1 * MIN
    assert "session=" in client.get("/me").headers["set-cookie"]


def test_rota_de_admin_tambem_respeita_a_inatividade(client, clock):
    assert client.get("/users").status_code == 200
    clock["t"] += 16 * MIN
    assert client.get("/users").status_code == 401
    assert client.get("/metrics/system").status_code == 401


def test_limite_absoluto_de_8_horas_mesmo_com_atividade(client, clock):
    resposta = None
    for _ in range(49):  # atividade a cada 10 min por 8h10
        clock["t"] += 10 * MIN
        resposta = client.get("/me")
        if resposta.status_code == 401:
            break
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == auth.EXPIRED_DETAIL
    assert clock["t"] > 0


def test_cookie_antigo_sem_horarios_continua_valendo_e_e_atualizado(client, clock):
    usuario = f"idle_{uuid.uuid4().hex[:8]}"
    criado = client.post("/users", json={"username": usuario, "password": "senha123"}).json()
    antigo = auth._get_serializer().dumps({"user_id": criado["id"], "v": 0})  # formato anterior à mudança

    with TestClient(app) as outro:
        outro.cookies.set("session", antigo)
        resposta = outro.get("/me")
        assert resposta.status_code == 200
        assert resposta.json()["username"] == usuario
        assert "session=" in resposta.headers["set-cookie"]  # já devolve no formato novo


def test_pagina_com_sessao_inativa_vai_para_o_login(client, clock):
    clock["t"] += 16 * MIN
    for caminho in ("/app", "/app/admin/users", "/", "/admin/users"):
        resposta = client.get(caminho)
        assert resposta.status_code in (302, 307) and resposta.headers["location"] == "/login", caminho


def test_depois_de_cair_e_possivel_entrar_de_novo(client, clock):
    clock["t"] += 16 * MIN
    assert client.get("/me").status_code == 401
    assert client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).status_code == 200
    assert client.get("/me").status_code == 200


def test_cookie_adulterado_continua_invalido(client):
    client.cookies.set("session", "valor-qualquer.adulterado.assinatura")
    resposta = client.get("/me")
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Sessão inválida"


def test_sessao_de_outro_usuario_nao_e_afetada(client, clock):
    """A inatividade é de cada cookie: quem fica parado cai, quem continua ativo permanece."""
    usuario = f"idle_{uuid.uuid4().hex[:8]}"
    client.post("/users", json={"username": usuario, "password": "senha123"})
    with TestClient(app) as outro:
        assert outro.post("/login", json={"username": usuario, "password": "senha123"}).status_code == 200
        clock["t"] += 10 * MIN
        assert outro.get("/me").status_code == 200  # só o outro usuário ficou ativo
        clock["t"] += 10 * MIN
        assert outro.get("/me").status_code == 200
        assert client.get("/me").status_code == 401  # o admin passou 20 min parado
