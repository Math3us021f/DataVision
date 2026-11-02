"""Painel padrão: regras determinísticas sobre o perfil, e todas as specs geradas precisam executar."""

import io
import os
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.analytics.engine import run_query
from src.services.analytics.suggestions import suggest_dashboard

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def col(name, type_, distinct, nulls=0):
    return {"column_name": name, "inferred_type": type_, "distinct_count": distinct, "null_count": nulls}


def charts(widgets):
    return [(w.title, w.spec.chart) for w in widgets]


def test_painel_completo_kpis_linha_e_categorias():
    profile = {
        "row_count": 100,
        "columns": [
            col("data", "datetime", 90),
            col("regiao", "text", 4),
            col("produto", "text", 12),
            col("valor", "float", 80),
            col("qtd", "integer", 15),
        ],
    }
    assert charts(suggest_dashboard(profile)) == [
        ("Soma de valor", "kpi"),
        ("Soma de qtd", "kpi"),
        ("Soma de valor por mês", "line"),
        ("Soma de valor por regiao", "pie"),   # 4 categorias: pizza
        ("Soma de valor por produto", "bar"),  # 12 categorias: barras
    ]


def test_poucas_datas_distintas_agrupam_por_dia():
    profile = {"row_count": 10, "columns": [col("data", "datetime", 10), col("v", "integer", 7)]}
    line = [w for w in suggest_dashboard(profile) if w.spec.chart == "line"][0]
    assert line.spec.dimension.time_grain == "day"


def test_identificadores_nao_viram_medida():
    profile = {
        "row_count": 50,
        "columns": [col("id", "integer", 50), col("user_id", "integer", 12), col("codigo", "integer", 9),
                    col("pedido_numero", "integer", 50), col("valor", "float", 30)],
    }
    kpis = [w.title for w in suggest_dashboard(profile) if w.spec.chart == "kpi"]
    # id/user_id/codigo pelo nome; pedido_numero por ser inteiro único e sem nulos em tabela grande
    assert kpis == ["Soma de valor"]


def test_sem_medida_usa_contagem_da_propria_coluna():
    profile = {"row_count": 100, "columns": [col("status", "text", 3), col("data", "datetime", 40)]}
    widgets = suggest_dashboard(profile)
    assert charts(widgets) == [("Contagem por mês", "line"), ("Contagem por status", "pie")]
    assert widgets[1].spec.metrics[0].agg == "count"


def test_texto_quase_unico_ou_coluna_vazia_nao_vira_categoria():
    profile = {
        "row_count": 200,
        "columns": [col("nome", "text", 190), col("constante", "text", 1), col("vazia", "float", 0, nulls=200)],
    }
    assert suggest_dashboard(profile) == []


def test_limita_a_tres_kpis_e_tres_categorias():
    profile = {
        "row_count": 100,
        "columns": [col(f"m{i}", "float", 50) for i in range(5)] + [col(f"c{i}", "text", 6) for i in range(5)],
    }
    widgets = suggest_dashboard(profile)
    assert sum(w.spec.chart == "kpi" for w in widgets) == 3
    assert sum(w.spec.chart in ("pie", "bar") for w in widgets) == 3


# ---------- Endpoint ----------

CSV = (
    b"data,cidade,valor\n"
    b"2026-01-10,SP,10\n2026-01-20,SP,20\n2026-02-05,RJ,5\n2026-02-15,RJ,15\n2026-03-01,MG,100\n"
)


@pytest.fixture
def logged_client():
    username = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})
    with TestClient(app) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


def upload(client) -> int:
    return client.post("/datasets/upload", files={"file": ("v.csv", io.BytesIO(CSV), "text/csv")}).json()["id"]


def test_painel_sugerido_no_upload_real_e_todas_as_specs_executam(logged_client):
    dataset_id = upload(logged_client)
    logged_client.post(f"/datasets/{dataset_id}/profile")

    response = logged_client.get(f"/datasets/{dataset_id}/suggested-dashboard")
    assert response.status_code == 200
    widgets = response.json()
    assert [(w["title"], w["spec"]["chart"]) for w in widgets] == [
        ("Soma de valor", "kpi"),
        ("Soma de valor por dia", "line"),
        ("Soma de valor por cidade", "pie"),
    ]

    # Cada spec devolvida precisa funcionar de verdade no endpoint de consulta, com números conferidos.
    results = [logged_client.post(f"/datasets/{dataset_id}/query", json=w["spec"]) for w in widgets]
    assert [r.status_code for r in results] == [200, 200, 200]
    assert results[0].json()["series"][0]["data"] == [150.0]
    assert dict(zip(results[2].json()["categories"], results[2].json()["series"][0]["data"])) == {
        "MG": 100.0, "SP": 30.0, "RJ": 20.0,
    }


def test_painel_sugerido_sem_perfil_retorna_409(logged_client):
    dataset_id = upload(logged_client)
    assert logged_client.get(f"/datasets/{dataset_id}/suggested-dashboard").status_code == 409


def test_painel_sugerido_de_outro_usuario_retorna_404(logged_client):
    dataset_id = upload(logged_client)
    logged_client.post(f"/datasets/{dataset_id}/profile")
    outro = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": outro, "password": "senha123"})
    with TestClient(app) as other:
        other.post("/login", json={"username": outro, "password": "senha123"})
        assert other.get(f"/datasets/{dataset_id}/suggested-dashboard").status_code == 404


def test_painel_sugerido_anonimo_retorna_401():
    with TestClient(app) as anon:
        assert anon.get("/datasets/1/suggested-dashboard").status_code == 401
