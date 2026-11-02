"""Dashboard salvo por dataset: ida e volta, validação contra o perfil, isolamento e cascata."""

import io
import os
import uuid

import pytest
from tests.compat import TestClient

from datasets.models import Dashboard, Dataset


def contar_dashboards(dataset_id):
    return Dashboard.objects.filter(dataset_id=dataset_id).count()
app = None

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

CSV = (
    b"data,cidade,valor\n"
    b"2026-01-10,SP,10\n2026-01-20,SP,20\n2026-02-05,RJ,5\n2026-02-15,RJ,15\n2026-03-01,MG,100\n"
)

KPI = {"chart": "kpi", "metrics": [{"column": "valor", "agg": "mean"}]}
BAR = {"chart": "bar", "dimension": {"column": "cidade"}, "metrics": [{"column": "valor", "agg": "sum"}]}
FILTER = {"column": "valor", "op": "gte", "value": 10}


def make_user(prefix="user"):
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})
    client = TestClient(app)
    client.post("/login", json={"username": username, "password": "senha123"})
    return client


@pytest.fixture
def client():
    with make_user() as c:
        yield c


def upload(client, profile=True) -> int:
    dataset_id = client.post("/datasets/upload", files={"file": ("v.csv", io.BytesIO(CSV), "text/csv")}).json()["id"]
    if profile:
        client.post(f"/datasets/{dataset_id}/profile")
    return dataset_id


def test_dataset_sem_dashboard_salvo_retorna_null(client):
    dataset_id = upload(client)
    response = client.get(f"/datasets/{dataset_id}/dashboard")
    assert response.status_code == 200
    assert response.json() is None


def test_salvar_e_ler_devolve_o_mesmo_conteudo(client):
    dataset_id = upload(client)
    saved = client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI, BAR], "filters": [FILTER]})
    assert saved.status_code == 200

    body = client.get(f"/datasets/{dataset_id}/dashboard").json()
    assert [w["chart"] for w in body["widgets"]] == ["kpi", "bar"]
    assert body["widgets"][0]["metrics"] == [{"column": "valor", "agg": "mean"}]
    assert body["widgets"][1]["dimension"]["column"] == "cidade"
    assert body["filters"] == [FILTER]
    assert body["updated_at"]


def test_salvar_de_novo_sobrescreve_sem_duplicar(client):
    dataset_id = upload(client)
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI, BAR]})
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [BAR]})

    assert [w["chart"] for w in client.get(f"/datasets/{dataset_id}/dashboard").json()["widgets"]] == ["bar"]
    assert contar_dashboards(dataset_id) == 1


def test_dashboard_salvo_continua_executavel_no_endpoint_de_consulta(client):
    dataset_id = upload(client)
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI]})
    saved = client.get(f"/datasets/{dataset_id}/dashboard").json()["widgets"][0]

    response = client.post(f"/datasets/{dataset_id}/query", json=saved)
    assert response.status_code == 200
    assert response.json()["series"][0]["data"] == [30.0]  # média de 10, 20, 5, 15, 100


def test_excluir_volta_para_null(client):
    dataset_id = upload(client)
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI]})
    assert client.delete(f"/datasets/{dataset_id}/dashboard").status_code == 204
    assert client.get(f"/datasets/{dataset_id}/dashboard").json() is None
    assert client.delete(f"/datasets/{dataset_id}/dashboard").status_code == 204  # idempotente


@pytest.mark.parametrize(
    "payload",
    [
        {"widgets": [{"chart": "bar", "dimension": {"column": "inexistente"}, "metrics": [{"column": "valor", "agg": "sum"}]}]},
        {"widgets": [{"chart": "bar", "dimension": {"column": "cidade"}, "metrics": [{"column": "cidade", "agg": "sum"}]}]},
        {"widgets": [KPI], "filters": [{"column": "cidade", "op": "gt", "value": "A"}]},  # filtro global inválido
        {"widgets": [KPI], "extra": "x"},
        {"widgets": [KPI] * 13},
        {"widgets": [{"chart": "kpi", "dimension": {"column": "cidade"}, "metrics": [{"column": "valor", "agg": "sum"}]}]},
    ],
)
def test_dashboard_invalido_e_rejeitado_com_422(client, payload):
    dataset_id = upload(client)
    assert client.put(f"/datasets/{dataset_id}/dashboard", json=payload).status_code == 422
    assert client.get(f"/datasets/{dataset_id}/dashboard").json() is None  # nada foi gravado


def test_salvar_sem_perfil_retorna_409(client):
    dataset_id = upload(client, profile=False)
    assert client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI]}).status_code == 409


def test_dataset_de_outro_usuario_retorna_404_em_tudo(client):
    dataset_id = upload(client)
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI]})

    with make_user() as other:
        assert other.get(f"/datasets/{dataset_id}/dashboard").status_code == 404
        assert other.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [BAR]}).status_code == 404
        assert other.delete(f"/datasets/{dataset_id}/dashboard").status_code == 404

    assert client.get(f"/datasets/{dataset_id}/dashboard").json()["widgets"][0]["chart"] == "kpi"  # intacto


def test_anonimo_retorna_401():
    with TestClient(app) as anon:
        assert anon.get("/datasets/1/dashboard").status_code == 401
        assert anon.put("/datasets/1/dashboard", json={"widgets": []}).status_code == 401
        assert anon.delete("/datasets/1/dashboard").status_code == 401


def test_excluir_o_dataset_apaga_o_dashboard_junto(client):
    dataset_id = upload(client)
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI]})

    assert client.delete(f"/datasets/{dataset_id}").status_code == 204
    assert contar_dashboards(dataset_id) == 0


def test_exclusao_forcada_do_usuario_apaga_dashboards(client):
    dataset_id = upload(client)
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [KPI]})
    owner = Dataset.objects.get(pk=dataset_id).owner_id

    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        assert admin.delete(f"/users/{owner}?force=true").status_code == 204

    assert contar_dashboards(dataset_id) == 0
