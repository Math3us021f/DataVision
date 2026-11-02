"""Proteções de recurso da consulta analítica: vagas limitadas, prazo de resposta e cache de arquivo."""

import io
import os
import threading
import time
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.routers.api.analytics as analytics_router
import src.services.datasets as datasets_service
from src.main import app
from src.services.analytics import runtime
from src.services.analytics.runtime import DataFrameCache, QueryBusyError, run_limited

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

CSV = b"cidade,valor\nSP,10\nSP,20\nRJ,5\n"
BODY = {"chart": "bar", "dimension": {"column": "cidade"}, "metrics": [{"column": "valor", "agg": "sum"}]}


# ---------- vagas ----------


def test_consulta_sem_vaga_desiste_com_erro_de_ocupado(monkeypatch):
    monkeypatch.setattr(runtime, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(runtime, "QUEUE_WAIT_SECONDS", 0.1)
    segurando, liberar = threading.Event(), threading.Event()

    def demorada():
        segurando.set()
        liberar.wait(2)
        return "ok"

    thread = threading.Thread(target=run_limited, args=(demorada,))
    thread.start()
    assert segurando.wait(2)
    with pytest.raises(QueryBusyError):
        run_limited(lambda: "nunca roda")

    liberar.set()
    thread.join(2)
    assert run_limited(lambda: "de novo") == "de novo"  # a vaga voltou


def test_vaga_e_devolvida_mesmo_quando_a_tarefa_falha(monkeypatch):
    monkeypatch.setattr(runtime, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(runtime, "QUEUE_WAIT_SECONDS", 0.1)

    def quebra():
        raise ValueError("falha qualquer")

    with pytest.raises(ValueError):
        run_limited(quebra)
    assert run_limited(lambda: 1) == 1


def test_nunca_passa_do_limite_de_consultas_simultaneas(monkeypatch):
    monkeypatch.setattr(runtime, "_slots", threading.BoundedSemaphore(2))
    monkeypatch.setattr(runtime, "QUEUE_WAIT_SECONDS", 5)
    agora, maximo, trava = 0, 0, threading.Lock()

    def tarefa():
        nonlocal agora, maximo
        with trava:
            agora += 1
            maximo = max(maximo, agora)
        time.sleep(0.05)
        with trava:
            agora -= 1

    threads = [threading.Thread(target=run_limited, args=(tarefa,)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join(5) for t in threads]
    assert maximo == 2


# ---------- cache ----------


def test_cache_le_o_arquivo_uma_vez_e_descarta_o_mais_antigo():
    cache, leituras = DataFrameCache(2), []

    def carregador(nome):
        def carregar():
            leituras.append(nome)
            return pd.DataFrame({"x": [1]})

        return carregar

    for chave in ["a", "a", "b", "a", "c", "a"]:  # "a" é reutilizado e por isso nunca é o mais antigo
        cache.get_or_load(chave, carregador(chave))
    assert leituras == ["a", "b", "c"]
    assert len(cache) == 2

    cache.get_or_load("b", carregador("b"))  # "b" tinha saído: lê de novo
    assert leituras == ["a", "b", "c", "b"]


def test_cache_evict_libera_o_arquivo():
    cache = DataFrameCache(2)
    cache.get_or_load("a", lambda: pd.DataFrame({"x": [1]}))
    cache.evict("a")
    cache.evict("inexistente")  # não é erro
    assert len(cache) == 0


# ---------- endpoint ----------


@pytest.fixture
def logged_client():
    username = f"lim_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})
    with TestClient(app) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


@pytest.fixture
def dataset_id(logged_client):
    response = logged_client.post("/datasets/upload", files={"file": ("v.csv", io.BytesIO(CSV), "text/csv")})
    new_id = response.json()["id"]
    assert logged_client.post(f"/datasets/{new_id}/profile").status_code == 200
    return new_id


def test_consulta_normal_continua_correta_e_repetida_usa_o_cache(logged_client, dataset_id, monkeypatch):
    cache = DataFrameCache(3)
    monkeypatch.setattr(runtime, "dataframe_cache", cache)
    monkeypatch.setattr(datasets_service, "dataframe_cache", cache)
    leituras = []
    original = runtime.load_dataframe
    monkeypatch.setattr(runtime, "load_dataframe", lambda *a: (leituras.append(a), original(*a))[1])

    for _ in range(3):
        resposta = logged_client.post(f"/datasets/{dataset_id}/query", json=BODY)
        assert resposta.status_code == 200
        assert resposta.json()["categories"] == ["SP", "RJ"]
        assert resposta.json()["series"][0]["data"] == [30.0, 5.0]
    assert len(leituras) == 1  # o arquivo veio do MinIO uma vez só
    assert len(cache) == 1

    assert logged_client.delete(f"/datasets/{dataset_id}").status_code == 204
    assert len(cache) == 0  # apagar o dataset libera a memória


def test_consulta_que_estoura_o_prazo_responde_504_e_devolve_a_vaga(logged_client, dataset_id, monkeypatch):
    monkeypatch.setattr(runtime, "QUERY_TIMEOUT_SECONDS", 0.2)
    original = analytics_router.run_query
    monkeypatch.setattr(analytics_router, "run_query", lambda *a: (time.sleep(1.0), original(*a))[1])

    inicio = time.monotonic()
    resposta = logged_client.post(f"/datasets/{dataset_id}/query", json=BODY)
    assert resposta.status_code == 504
    assert "demorou demais" in resposta.json()["detail"]
    assert time.monotonic() - inicio < 0.9  # respondeu no prazo, sem esperar a thread acabar

    # a thread abandonada termina sozinha e a vaga volta
    for _ in range(40):
        if runtime._slots._value == runtime.MAX_CONCURRENT_QUERIES:
            break
        time.sleep(0.1)
    assert runtime._slots._value == runtime.MAX_CONCURRENT_QUERIES


def test_sem_vaga_a_consulta_responde_503(logged_client, dataset_id, monkeypatch):
    ocupado = threading.BoundedSemaphore(1)
    ocupado.acquire()
    monkeypatch.setattr(runtime, "_slots", ocupado)
    monkeypatch.setattr(runtime, "QUEUE_WAIT_SECONDS", 0.1)

    resposta = logged_client.post(f"/datasets/{dataset_id}/query", json=BODY)
    assert resposta.status_code == 503
    assert "ocupado" in resposta.json()["detail"]


def test_erros_de_validacao_e_dono_continuam_iguais(logged_client, dataset_id):
    ruim = {"chart": "bar", "dimension": {"column": "nao_existe"}, "metrics": [{"column": "valor", "agg": "sum"}]}
    assert logged_client.post(f"/datasets/{dataset_id}/query", json=ruim).status_code == 422
    assert logged_client.post("/datasets/99999999/query", json=BODY).status_code == 404
    with TestClient(app) as anonimo:
        assert anonimo.post(f"/datasets/{dataset_id}/query", json=BODY).status_code == 401
