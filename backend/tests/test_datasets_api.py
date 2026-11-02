"""Datasets: upload com validação, listagem, exclusão, perfilamento com números exatos e amostra."""

import io
import re

import pandas as pd
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from analytics.runtime import dataframe_cache
from datasets.models import Dashboard, Dataset, DatasetColumn, DatasetColumnTopValue, DatasetProfile
from tests.conftest import ApiClient, logged_client, make_user

User = get_user_model()
pytestmark = pytest.mark.django_db

CSV = (
    b"cidade,valor,data\n"
    b"SP,10,2026-01-10\nSP,20,2026-02-05\nRJ,5,2026-02-15\nRJ,15,2026-03-01\nMG,100,2026-03-10\n"
    b"SP,10,2026-01-10\n"  # linha repetida: conta como duplicada
)


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        pass

    def release_conn(self):
        pass


class FakeMinio:
    """MinIO em memória: guarda os arquivos num dicionário."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, bucket, key, data, length):
        self.objects[(bucket, key)] = data.read()

    def get_object(self, bucket, key):
        return FakeResponse(self.objects[(bucket, key)])

    def remove_object(self, bucket, key):
        self.objects.pop((bucket, key), None)


@pytest.fixture(autouse=True)
def minio(monkeypatch):
    fake = FakeMinio()
    monkeypatch.setenv("MINIO_BUCKET", "bucket-de-teste")
    monkeypatch.setattr("core.storage.get_minio_client", lambda: fake)
    return fake


def enviar(cliente, nome="vendas.csv", conteudo=CSV, tipo="text/csv"):
    return cliente.post("/datasets/upload", {"file": SimpleUploadedFile(nome, conteudo, content_type=tipo)})


def xlsx(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture
def dono():
    return make_user("dono")


@pytest.fixture
def cliente(dono):
    return logged_client(dono)


@pytest.fixture
def dataset_id(cliente):
    return enviar(cliente).json()["id"]


# ---------- login e CSRF ----------


@pytest.mark.parametrize("metodo, caminho", [("get", "/datasets"), ("post", "/datasets/upload"), ("delete", "/datasets/1"), ("post", "/datasets/1/profile"), ("get", "/datasets/1/profile"), ("get", "/datasets/1/sample")])
def test_anonimo_recebe_401(metodo, caminho):
    assert getattr(ApiClient(), metodo)(caminho).status_code == 401


def test_upload_e_exclusao_exigem_o_token_csrf(dono, minio):
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.force_login(dono)
    assert enviar(cliente).status_code == 403 and minio.objects == {}
    assert cliente.get("/datasets").status_code == 200  # leitura não precisa


# ---------- upload ----------


def test_upload_guarda_o_arquivo_no_minio_com_nome_gerado_pelo_servidor(cliente, dono, minio):
    resposta = enviar(cliente, "meu arquivo.csv")
    assert resposta.status_code == 201
    assert resposta.json() == {"id": resposta.json()["id"], "original_name": "meu arquivo.csv", "format": ".csv", "size_bytes": len(CSV), "created_at": None, "profiled": False}
    (bucket, chave), conteudo = next(iter(minio.objects.items()))
    assert bucket == "bucket-de-teste" and re.fullmatch(r"[0-9a-f]{32}\.csv", chave) and conteudo == CSV  # nunca o nome do usuário
    assert Dataset.objects.get().owner == dono


def test_upload_de_xlsx_valido(cliente):
    conteudo = xlsx(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}))
    resposta = enviar(cliente, "planilha.xlsx", conteudo, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert resposta.status_code == 201 and resposta.json()["format"] == ".xlsx"


@pytest.mark.parametrize("nome", ["foto.png", "programa.exe", "script.py", "sem_extensao", "dados.csv.exe", "dados.xls", ".csv.", "dados"])
def test_extensao_nao_permitida_da_403(cliente, minio, nome):
    assert enviar(cliente, nome).status_code == 403 and minio.objects == {} and not Dataset.objects.exists()


def test_extensao_maiuscula_e_aceita(cliente):
    resposta = enviar(cliente, "DADOS.CSV")
    assert resposta.status_code == 201 and resposta.json()["format"] == ".csv"


def test_arquivo_grande_demais_da_413_sem_guardar_nada(cliente, minio):
    limite = b"a\n" + b"1\n" * 4_999_999  # 2 + 9.999.998 = exatamente 10.000.000 bytes
    assert len(limite) == 10_000_000
    assert enviar(cliente, "limite.csv", limite).status_code == 201  # no limite ainda vale
    minio.objects.clear()
    Dataset.objects.all().delete()

    grande = enviar(cliente, "grande.csv", limite + b"1")  # 1 byte a mais
    assert grande.status_code == 413 and grande.json()["detail"] == "Arquivo grande demais"
    assert minio.objects == {} and not Dataset.objects.exists()


@pytest.mark.parametrize(
    "nome, conteudo",
    [
        ("falso.csv", b"a,b\n1,\x00\n"),  # byte nulo: arquivo binário disfarçado
        ("latin1.csv", "cidade\nS\xe3o Paulo\n".encode("latin-1")),  # não é UTF-8
        ("falso.xlsx", b"isto nao e uma planilha"),
        ("zip.csv", xlsx(pd.DataFrame({"a": [1]}))),  # planilha com extensão de CSV
    ],
)
def test_conteudo_que_nao_bate_com_a_extensao_da_400(cliente, minio, nome, conteudo):
    resposta = enviar(cliente, nome, conteudo)
    assert resposta.status_code == 400 and "não corresponde ao formato" in resposta.json()["detail"]
    assert minio.objects == {} and not Dataset.objects.exists()


def test_nome_com_caminho_nao_vira_caminho_no_minio(cliente, minio):
    enviar(cliente, "../../etc/passwd.csv")
    (_, chave) = next(iter(minio.objects))
    assert ".." not in chave and "/" not in chave and "passwd" not in chave
    assert ".." not in Dataset.objects.get().original_name and "/" not in Dataset.objects.get().original_name


def test_nome_malicioso_volta_como_texto_puro(cliente):
    nome = "<img src=x onerror=alert(1)>.csv"
    assert enviar(cliente, nome).json()["original_name"] == nome  # a interface escapa ao exibir; o servidor não altera nem interpreta
    assert cliente.get("/datasets").json()[0]["original_name"] == nome


def test_upload_sem_o_campo_file_da_422(cliente):
    assert cliente.post("/datasets/upload", {}).status_code == 422


# ---------- listagem ----------


def test_lista_so_os_meus_datasets_do_mais_novo_para_o_mais_antigo(cliente, dono):
    primeiro, segundo = enviar(cliente, "a.csv").json()["id"], enviar(cliente, "b.csv").json()["id"]
    outro = logged_client(make_user("outro"))
    enviar(outro, "alheio.csv")
    cliente.post(f"/datasets/{primeiro}/profile")

    lista = cliente.get("/datasets").json()
    assert [(d["id"], d["original_name"], d["profiled"]) for d in lista] == [(segundo, "b.csv", False), (primeiro, "a.csv", True)]
    assert all(d["created_at"] and d["format"] == ".csv" and d["size_bytes"] == len(CSV) for d in lista)
    assert [d["original_name"] for d in outro.get("/datasets").json()] == ["alheio.csv"]


def test_lista_vazia_para_quem_nao_enviou_nada(cliente):
    assert cliente.get("/datasets").json() == []


# ---------- exclusão ----------


def test_excluir_apaga_o_arquivo_o_perfil_as_colunas_e_o_dashboard(cliente, dono, dataset_id, minio):
    cliente.post(f"/datasets/{dataset_id}/profile")
    Dashboard.objects.create(dataset_id=dataset_id, owner=dono, spec={})
    assert minio.objects and DatasetProfile.objects.exists() and DatasetColumnTopValue.objects.exists()

    assert cliente.delete(f"/datasets/{dataset_id}").status_code == 204
    assert minio.objects == {} and not Dataset.objects.exists()
    assert not DatasetProfile.objects.exists() and not DatasetColumn.objects.exists()
    assert not DatasetColumnTopValue.objects.exists() and not Dashboard.objects.exists()


def test_excluir_libera_o_arquivo_da_memoria(cliente, dataset_id):
    chave = Dataset.objects.get().object_key
    dataframe_cache.get_or_load(chave, lambda: pd.DataFrame({"x": [1]}))
    assert len(dataframe_cache) >= 1
    cliente.delete(f"/datasets/{dataset_id}")
    assert chave not in dataframe_cache._items


def test_falha_no_minio_nao_trava_a_exclusao(cliente, dataset_id, monkeypatch):
    class Quebrado:
        def remove_object(self, *args):
            raise OSError("MinIO fora do ar")

    monkeypatch.setattr("core.storage.get_minio_client", lambda: Quebrado())
    assert cliente.delete(f"/datasets/{dataset_id}").status_code == 204 and not Dataset.objects.exists()


@pytest.mark.parametrize("metodo, sufixo", [("delete", ""), ("post", "/profile"), ("get", "/profile"), ("get", "/sample")])
def test_dataset_de_outro_usuario_ou_inexistente_da_404_igual(dataset_id, metodo, sufixo):
    invasor = logged_client(make_user("invasor"))
    alheio = getattr(invasor, metodo)(f"/datasets/{dataset_id}{sufixo}")
    inexistente = getattr(invasor, metodo)(f"/datasets/99999999{sufixo}")
    assert alheio.status_code == inexistente.status_code == 404
    assert alheio.json() == inexistente.json() == {"detail": "Dataset não encontrado"}  # não revela que existe
    assert Dataset.objects.filter(pk=dataset_id).exists()


def test_id_que_nao_e_numero_da_404(cliente):
    assert cliente.get("/datasets/abc/profile").status_code == 404


# ---------- perfilamento ----------


def por_nome(perfil):
    return {c["column_name"]: c for c in perfil["columns"]}


def test_perfil_com_numeros_conferidos_a_mao(cliente, dataset_id):
    resposta = cliente.post(f"/datasets/{dataset_id}/profile")
    assert resposta.status_code == 200
    perfil = resposta.json()
    assert perfil["row_count"] == 6 and perfil["duplicate_row_count"] == 1
    colunas = por_nome(perfil)
    assert [c["column_name"] for c in perfil["columns"]] == ["cidade", "valor", "data"]

    cidade, valor, data = colunas["cidade"], colunas["valor"], colunas["data"]
    assert (cidade["inferred_type"], cidade["distinct_count"], cidade["null_count"]) == ("text", 3, 0)
    assert {t["value"]: t["count"] for t in cidade["top_values"]} == {"SP": 3, "RJ": 2, "MG": 1}
    assert cidade["top_values"][0] == {"value": "SP", "count": 3}  # os mais frequentes primeiro
    assert cidade["histogram"] is None and cidade["min_value"] is None

    assert (valor["inferred_type"], valor["distinct_count"], valor["null_count"]) == ("integer", 5, 0)
    assert (valor["min_value"], valor["max_value"], valor["median_value"]) == (5.0, 100.0, 12.5)
    assert valor["mean_value"] == pytest.approx(160 / 6) and valor["top_values"] is None
    assert sum(valor["histogram"]["counts"]) == 6 and len(valor["histogram"]["bin_edges"]) == len(valor["histogram"]["counts"]) + 1

    assert (data["inferred_type"], data["distinct_count"]) == ("datetime", 5)


def test_perfil_salvo_e_igual_ao_calculado(cliente, dataset_id):
    calculado = cliente.post(f"/datasets/{dataset_id}/profile").json()
    assert cliente.get(f"/datasets/{dataset_id}/profile").json() == calculado


def test_perfil_antes_de_calcular_da_404_com_mensagem(cliente, dataset_id):
    resposta = cliente.get(f"/datasets/{dataset_id}/profile")
    assert resposta.status_code == 404 and resposta.json()["detail"] == "Este dataset ainda não foi perfilado"


def test_perfilar_de_novo_substitui_sem_duplicar(cliente, dataset_id):
    cliente.post(f"/datasets/{dataset_id}/profile")
    cliente.post(f"/datasets/{dataset_id}/profile")
    assert DatasetProfile.objects.count() == 1 and DatasetColumn.objects.count() == 3
    assert DatasetColumnTopValue.objects.count() == 3  # SP, RJ, MG: sem repetição do perfil anterior


def test_perfil_de_planilha_xlsx(cliente):
    conteudo = xlsx(pd.DataFrame({"n": [1, 2, 3, 4], "t": ["a", "b", "a", None]}))
    identificador = enviar(cliente, "p.xlsx", conteudo).json()["id"]
    perfil = cliente.post(f"/datasets/{identificador}/profile").json()
    colunas = por_nome(perfil)
    assert perfil["row_count"] == 4 and colunas["n"]["mean_value"] == 2.5 and colunas["t"]["null_count"] == 1


def test_valores_ausentes_sao_contados(cliente):
    identificador = enviar(cliente, "n.csv", b"a,b\n1,x\n,y\n3,\n").json()["id"]
    colunas = por_nome(cliente.post(f"/datasets/{identificador}/profile").json())
    assert colunas["a"]["null_count"] == 1 and colunas["b"]["null_count"] == 1


# ---------- amostra ----------


def test_amostra_limita_a_20_linhas_e_devolve_texto(cliente):
    linhas = b"n,t\n" + b"".join(f"{i},linha{i}\n".encode() for i in range(30))
    identificador = enviar(cliente, "grande.csv", linhas).json()["id"]
    amostra = cliente.get(f"/datasets/{identificador}/sample").json()
    assert amostra["columns"] == ["n", "t"] and amostra["total_rows"] == 30 and amostra["sample_size"] == 20
    assert amostra["rows"][0] == ["0", "linha0"] and amostra["rows"][19] == ["19", "linha19"] and len(amostra["rows"]) == 20


def test_amostra_mostra_celula_vazia_como_nulo(cliente):
    identificador = enviar(cliente, "v.csv", b"a,b\n1,\n,y\n").json()["id"]
    assert cliente.get(f"/datasets/{identificador}/sample").json()["rows"] == [["1.0", None], [None, "y"]]


def test_amostra_nao_interpreta_html_do_arquivo(cliente):
    identificador = enviar(cliente, "x.csv", b"nome\n<script>alert(1)</script>\n").json()["id"]
    assert cliente.get(f"/datasets/{identificador}/sample").json()["rows"] == [["<script>alert(1)</script>"]]  # texto puro


def test_amostra_de_planilha(cliente):
    identificador = enviar(cliente, "p.xlsx", xlsx(pd.DataFrame({"a": [1, 2]}))).json()["id"]
    amostra = cliente.get(f"/datasets/{identificador}/sample").json()
    assert amostra["columns"] == ["a"] and amostra["rows"] == [["1"], ["2"]] and amostra["total_rows"] == 2
