"""Testes de perfilamento de datasets (Etapa 10). Confere números exatos, não só 'funcionou'."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

CSV_CONHECIDO = b"nome,idade,cidade\nAna,30,SP\nBruno,25,RJ\nCarla,,SP\nAna,30,SP\n"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def logged_client():
    username = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": username, "password": "senha123"})

    with TestClient(app) as c:
        c.post("/login", json={"username": username, "password": "senha123"})
        yield c


def upload(client, filename: str, content: bytes) -> int:
    response = client.post(
        "/datasets/upload", files={"file": (filename, io.BytesIO(content), "application/octet-stream")}
    )
    return response.json()["id"]


def test_perfilamento_calcula_numeros_exatos(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    response = logged_client.post(f"/datasets/{dataset_id}/profile")
    assert response.status_code == 200

    body = response.json()
    assert body["row_count"] == 4
    assert body["duplicate_row_count"] == 1

    por_nome = {c["column_name"]: c for c in body["columns"]}

    # Colunas de texto não têm estatística numérica, mas têm os valores mais frequentes.
    nome = por_nome["nome"]
    assert nome["inferred_type"] == "text"
    assert nome["null_count"] == 0
    assert nome["distinct_count"] == 3
    assert nome["min_value"] is None
    top_nome = {t["value"]: t["count"] for t in nome["top_values"]}
    assert top_nome == {"Ana": 2, "Bruno": 1, "Carla": 1}

    cidade = por_nome["cidade"]
    top_cidade = {t["value"]: t["count"] for t in cidade["top_values"]}
    assert top_cidade == {"SP": 3, "RJ": 1}

    # idade: valores não-nulos são [30, 25, 30] — min=25, max=30, média=85/3, mediana=30.
    idade = por_nome["idade"]
    assert idade["inferred_type"] == "float"
    assert idade["null_count"] == 1
    assert idade["distinct_count"] == 2
    assert idade["min_value"] == 25.0
    assert idade["max_value"] == 30.0
    assert idade["mean_value"] == pytest.approx(85 / 3)
    assert idade["median_value"] == 30.0


def test_top_values_limita_a_5_e_coluna_numerica_nao_tem(logged_client):
    linhas = "\n".join(f"item{i}" for i in range(8))
    csv = f"categoria\n{linhas}\n".encode()
    dataset_id = upload(logged_client, "categorias.csv", csv)

    response = logged_client.post(f"/datasets/{dataset_id}/profile")
    categoria = response.json()["columns"][0]

    assert len(categoria["top_values"]) == 5
    assert all(t["count"] == 1 for t in categoria["top_values"])


def test_recalcular_nao_duplica_top_values(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)
    logged_client.post(f"/datasets/{dataset_id}/profile")
    second = logged_client.post(f"/datasets/{dataset_id}/profile")

    nome = next(c for c in second.json()["columns"] if c["column_name"] == "nome")
    assert len(nome["top_values"]) == 3  # Ana, Bruno, Carla — não 6


def test_histograma_de_coluna_numerica(logged_client):
    valores = "\n".join(str(v) for v in range(1, 11))  # 1 a 10
    csv = f"valor\n{valores}\n".encode()
    dataset_id = upload(logged_client, "histograma.csv", csv)

    response = logged_client.post(f"/datasets/{dataset_id}/profile")
    coluna = response.json()["columns"][0]

    assert coluna["histogram"]["bin_edges"][0] == 1.0
    assert coluna["histogram"]["bin_edges"][-1] == 10.0
    assert len(coluna["histogram"]["bin_edges"]) == 11  # 10 faixas = 11 limites
    assert len(coluna["histogram"]["counts"]) == 10
    assert sum(coluna["histogram"]["counts"]) == 10  # todo valor caiu em alguma faixa


def test_coluna_de_texto_nao_tem_histograma(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)
    response = logged_client.post(f"/datasets/{dataset_id}/profile")

    nome = next(c for c in response.json()["columns"] if c["column_name"] == "nome")
    assert nome["histogram"] is None


def test_coluna_numerica_totalmente_vazia_nao_tem_estatistica(logged_client):
    csv_com_coluna_vazia = b"nome,valor\nAna,\nBruno,\n"
    dataset_id = upload(logged_client, "vazio.csv", csv_com_coluna_vazia)

    response = logged_client.post(f"/datasets/{dataset_id}/profile")
    valor = next(c for c in response.json()["columns"] if c["column_name"] == "valor")

    assert valor["null_count"] == 2
    assert valor["min_value"] is None
    assert valor["max_value"] is None
    assert valor["mean_value"] is None
    assert valor["median_value"] is None
    assert valor["histogram"] is None


def test_get_profile_retorna_o_que_foi_calculado(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)
    logged_client.post(f"/datasets/{dataset_id}/profile")

    response = logged_client.get(f"/datasets/{dataset_id}/profile")
    assert response.status_code == 200
    assert response.json()["row_count"] == 4


def test_get_profile_antes_de_perfilar_retorna_404(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    response = logged_client.get(f"/datasets/{dataset_id}/profile")
    assert response.status_code == 404


def test_reperfilar_substitui_sem_duplicar(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    logged_client.post(f"/datasets/{dataset_id}/profile")
    segunda = logged_client.post(f"/datasets/{dataset_id}/profile")

    assert segunda.status_code == 200
    assert len(segunda.json()["columns"]) == 3  # não dobrou pra 6


def test_dataset_de_outro_usuario_retorna_404(logged_client):
    dataset_id = upload(logged_client, "dados.csv", CSV_CONHECIDO)

    outro_username = f"user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        admin.post("/users", json={"username": outro_username, "password": "senha123"})

    with TestClient(app) as outro_client:
        outro_client.post("/login", json={"username": outro_username, "password": "senha123"})
        response = outro_client.post(f"/datasets/{dataset_id}/profile")
        assert response.status_code == 404


def test_dataset_inexistente_retorna_404(logged_client):
    response = logged_client.post("/datasets/999999/profile")
    assert response.status_code == 404


def test_anonimo_nao_pode_perfilar(client):
    response = client.post("/datasets/1/profile")
    assert response.status_code == 401
