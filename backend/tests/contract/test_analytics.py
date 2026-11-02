"""Motor de consultas do dashboard: números conferidos à mão + casos negativos."""

import io
import os
import uuid

import pandas as pd
import pytest
from tests.compat import TestClient
from pydantic import ValidationError

app = None
from analytics.schemas import QuerySpec
from analytics.engine import run_query
from analytics.validator import InvalidQueryError
from datasets.profiling import infer_column_type, parse_datetimes

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

CSV = (
    b"data,cidade,valor\n"
    b"2026-01-10,SP,10\n2026-01-20,SP,20\n2026-02-05,RJ,5\n2026-02-15,RJ,15\n2026-03-01,MG,100\n"
)
TYPES = {"data": "datetime", "cidade": "text", "valor": "integer"}


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(CSV))


def spec(**kwargs) -> QuerySpec:
    return QuerySpec.model_validate(kwargs)


# ---------- Inferência de datetime ----------

def test_data_iso_e_brasileira_viram_datetime():
    assert infer_column_type(pd.Series(["2026-01-10", "2026-02-05"])) == "datetime"
    assert infer_column_type(pd.Series(["10/01/2026", "05/02/2026"])) == "datetime"


def test_codigos_numericos_em_texto_continuam_texto():
    assert infer_column_type(pd.Series(["12345", "67890", "11111"])) == "text"


def test_coluna_com_muitas_datas_invalidas_continua_texto():
    valores = ["2026-01-10"] * 9 + ["2026-13-45"] * 1  # 90% válido, abaixo do limite de 95%
    assert infer_column_type(pd.Series(valores)) == "text"


def test_dayfirst_interpreta_dia_antes_do_mes():
    assert parse_datetimes(pd.Series(["01/02/2026"])).iloc[0] == pd.Timestamp("2026-02-01")


def test_data_iso_nao_tem_dia_e_mes_trocados():
    parsed = parse_datetimes(pd.Series(["2026-01-10", "10/01/2026", "2026-03-01"]))
    assert list(parsed) == [pd.Timestamp("2026-01-10"), pd.Timestamp("2026-01-10"), pd.Timestamp("2026-03-01")]


# ---------- Engine ----------

def test_soma_por_categoria_ordenada_do_maior_para_o_menor(df):
    result = run_query(
        df,
        spec(chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}]),
        TYPES,
    )
    assert result["categories"] == ["MG", "SP", "RJ"]
    assert result["series"][0]["data"] == [100.0, 30.0, 20.0]
    assert result["series"][0]["name"] == "Soma de valor"
    assert result["truncated"] is False


def test_filtro_gte(df):
    result = run_query(
        df,
        spec(
            chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}],
            filters=[{"column": "valor", "op": "gte", "value": 15}],
        ),
        TYPES,
    )
    assert result["total_rows_matched"] == 3  # 20, 15 e 100
    assert dict(zip(result["categories"], result["series"][0]["data"])) == {"SP": 20.0, "RJ": 15.0, "MG": 100.0}


def test_filtro_in_e_contains(df):
    in_result = run_query(
        df,
        spec(chart="kpi", metrics=[{"column": "valor", "agg": "sum"}],
             filters=[{"column": "cidade", "op": "in", "value": ["SP", "MG"]}]),
        TYPES,
    )
    assert in_result["series"][0]["data"] == [130.0]

    contains_result = run_query(
        df,
        spec(chart="kpi", metrics=[{"column": "valor", "agg": "count"}],
             filters=[{"column": "cidade", "op": "contains", "value": "s"}]),
        TYPES,
    )
    assert contains_result["series"][0]["data"] == [2.0]  # só "SP", sem diferenciar maiúscula


def test_agrupamento_mensal_ordenado_por_tempo(df):
    result = run_query(
        df,
        spec(chart="line", dimension={"column": "data", "time_grain": "month"},
             metrics=[{"column": "valor", "agg": "sum"}]),
        TYPES,
    )
    assert result["categories"] == ["2026-01", "2026-02", "2026-03"]
    assert result["series"][0]["data"] == [30.0, 20.0, 100.0]


def test_kpi_soma_total(df):
    result = run_query(df, spec(chart="kpi", metrics=[{"column": "valor", "agg": "sum"}]), TYPES)
    assert result["categories"] == []
    assert result["series"][0]["data"] == [150.0]


def test_limite_marca_truncated(df):
    result = run_query(
        df,
        spec(chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}], limit=2),
        TYPES,
    )
    assert result["truncated"] is True
    assert result["categories"] == ["MG", "SP"]


def test_regex_no_contains_e_tratado_como_texto_literal(df):
    result = run_query(
        df,
        spec(chart="kpi", metrics=[{"column": "valor", "agg": "count"}],
             filters=[{"column": "cidade", "op": "contains", "value": ".*"}]),
        TYPES,
    )
    assert result["series"][0]["data"] == [0.0]  # se fosse regex, casaria com tudo


@pytest.mark.parametrize(
    "payload",
    [
        dict(chart="bar", dimension={"column": "inexistente"}, metrics=[{"column": "valor", "agg": "sum"}]),
        dict(chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "cidade", "agg": "mean"}]),
        dict(chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}],
             filters=[{"column": "valor", "op": "contains", "value": "1"}]),
        dict(chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}],
             filters=[{"column": "valor", "op": "gt", "value": "abc"}]),
        dict(chart="bar", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}],
             filters=[{"column": "cidade", "op": "in", "value": "SP"}]),
        dict(chart="bar", dimension={"column": "cidade", "time_grain": "month"},
             metrics=[{"column": "valor", "agg": "sum"}]),
    ],
)
def test_specs_invalidas_levantam_erro(df, payload):
    with pytest.raises(InvalidQueryError):
        run_query(df, spec(**payload), TYPES)


def test_chave_desconhecida_e_rejeitada_pelo_schema():
    with pytest.raises(ValidationError):
        spec(chart="kpi", metrics=[{"column": "valor", "agg": "sum"}], code="__import__('os')")


def test_kpi_com_dimensao_e_rejeitado_pelo_schema():
    with pytest.raises(ValidationError):
        spec(chart="kpi", dimension={"column": "cidade"}, metrics=[{"column": "valor", "agg": "sum"}])


# ---------- Endpoint ----------

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
    response = client.post("/datasets/upload", files={"file": ("vendas.csv", io.BytesIO(CSV), "text/csv")})
    return response.json()["id"]


BODY = {"chart": "bar", "dimension": {"column": "cidade"}, "metrics": [{"column": "valor", "agg": "sum"}]}


def test_query_endpoint_retorna_dados_conferidos(logged_client):
    dataset_id = upload(logged_client)
    logged_client.post(f"/datasets/{dataset_id}/profile")

    response = logged_client.post(f"/datasets/{dataset_id}/query", json=BODY)
    assert response.status_code == 200
    body = response.json()
    assert body["categories"] == ["MG", "SP", "RJ"]
    assert body["series"][0]["data"] == [100.0, 30.0, 20.0]


def test_perfil_detecta_coluna_de_data_no_upload_real(logged_client):
    dataset_id = upload(logged_client)
    profile = logged_client.post(f"/datasets/{dataset_id}/profile").json()
    por_nome = {c["column_name"]: c for c in profile["columns"]}
    assert por_nome["data"]["inferred_type"] == "datetime"


def test_query_sem_perfil_retorna_409(logged_client):
    dataset_id = upload(logged_client)
    assert logged_client.post(f"/datasets/{dataset_id}/query", json=BODY).status_code == 409


def test_query_invalida_retorna_422(logged_client):
    dataset_id = upload(logged_client)
    logged_client.post(f"/datasets/{dataset_id}/profile")
    bad = {**BODY, "metrics": [{"column": "cidade", "agg": "sum"}]}
    assert logged_client.post(f"/datasets/{dataset_id}/query", json=bad).status_code == 422


def test_query_de_dataset_de_outro_usuario_retorna_404(logged_client):
    dataset_id = upload(logged_client)
    logged_client.post(f"/datasets/{dataset_id}/profile")

    outro = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": outro, "password": "senha123"})
    with TestClient(app) as other:
        other.post("/login", json={"username": outro, "password": "senha123"})
        assert other.post(f"/datasets/{dataset_id}/query", json=BODY).status_code == 404


def test_query_anonima_retorna_401():
    with TestClient(app) as anon:
        assert anon.post("/datasets/1/query", json=BODY).status_code == 401
