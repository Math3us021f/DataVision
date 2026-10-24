"""Testes do explorador de arquivos (Etapa 7). Foco em path traversal."""

import os

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.routers.files import ALLOWED_ROOT

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_client():
    with TestClient(app) as c:
        c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        yield c


@pytest.fixture
def sample_file():
    """Cria um arquivo .csv temporário dentro de ALLOWED_ROOT para os testes de leitura."""
    file_path = os.path.join(ALLOWED_ROOT, "_teste_pytest.csv")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("a,b\n1,2\n")
    yield "_teste_pytest.csv"
    os.remove(file_path)


def test_lista_raiz(admin_client):
    response = admin_client.get("/files")
    assert response.status_code == 200
    assert "entries" in response.json()


def test_le_arquivo_permitido(admin_client, sample_file):
    response = admin_client.get("/files/content", params={"path": sample_file})
    assert response.status_code == 200
    assert response.json()["content"] == "a,b\n1,2\n"


def test_extensao_nao_permitida_e_bloqueada(admin_client):
    blocked_path = os.path.join(ALLOWED_ROOT, "_teste_bloqueado.env")
    with open(blocked_path, "w", encoding="utf-8") as f:
        f.write("SEGREDO=123")
    try:
        response = admin_client.get("/files/content", params={"path": "_teste_bloqueado.env"})
        assert response.status_code == 403
    finally:
        os.remove(blocked_path)


@pytest.mark.parametrize(
    "ataque",
    [
        "../../../../etc/passwd",
        "subpasta/../../etc",
    ],
)
def test_path_traversal_relativo_e_bloqueado(admin_client, ataque):
    """Casos onde '..' realmente aparece como componente de caminho: deve ser 400 (bloqueado na validação)."""
    response = admin_client.get("/files", params={"path": ataque})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "ataque",
    [
        "..%2f..%2f..%2fetc%2fpasswd",  # %2f como texto literal (o cliente HTTP escapa o %), não vira barra real
        "....//....//etc",  # "...." não tem significado especial no filesystem, não é traversal de verdade
    ],
)
def test_path_nao_existente_e_404_nao_escapa(admin_client, ataque):
    """Esses payloads nunca chegam a escapar de data/ — resolvem para um caminho inexistente dentro dela (404)."""
    response = admin_client.get("/files", params={"path": ataque})
    assert response.status_code == 404


def test_path_traversal_codificado_na_url_crua_e_bloqueado(admin_client):
    """Simula a URL já com %2F literal na querystring (sem o httpx re-escapar), o cenário real de ataque."""
    response = admin_client.get("/files?path=..%2F..%2F..%2F..%2Fetc")
    assert response.status_code == 400


def test_path_absoluto_e_bloqueado(admin_client):
    response = admin_client.get("/files", params={"path": "/etc"})
    assert response.status_code == 400


def test_symlink_escapando_e_bloqueado(admin_client):
    link_path = os.path.join(ALLOWED_ROOT, "_teste_symlink_escape")
    os.symlink("/etc/passwd", link_path)
    try:
        response = admin_client.get("/files/content", params={"path": "_teste_symlink_escape"})
        assert response.status_code == 400
    finally:
        os.remove(link_path)


def test_symlink_nao_aparece_na_listagem(admin_client):
    link_path = os.path.join(ALLOWED_ROOT, "_teste_symlink_listagem")
    os.symlink("/etc/passwd", link_path)
    try:
        response = admin_client.get("/files")
        names = [e["name"] for e in response.json()["entries"]]
        assert "_teste_symlink_listagem" not in names
    finally:
        os.remove(link_path)


def test_arquivo_inexistente_retorna_404(admin_client):
    response = admin_client.get("/files/content", params={"path": "nao_existe.csv"})
    assert response.status_code == 404


def test_anonimo_nao_acessa_explorador(client):
    response = client.get("/files")
    assert response.status_code == 401


def test_nao_admin_nao_acessa_explorador(admin_client):
    import uuid

    username = f"user_{uuid.uuid4().hex[:8]}"
    admin_client.post("/users", json={"username": username, "password": "senha123"})

    non_admin_client = TestClient(app)
    non_admin_client.post("/login", json={"username": username, "password": "senha123"})

    response = non_admin_client.get("/files")
    assert response.status_code == 403
