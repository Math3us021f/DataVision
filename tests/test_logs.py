"""Testes do endpoint de logs da aplicação (Etapa 6)."""

import os

import pytest
from fastapi.testclient import TestClient

from src.main import app

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


def test_admin_le_logs(admin_client):
    response = admin_client.get("/logs/app")
    assert response.status_code == 200
    assert "lines" in response.json()


def test_login_falho_aparece_no_log(client, admin_client):
    client.post("/login", json={"username": ADMIN_USERNAME, "password": "senha-errada-de-proposito"})

    logs = admin_client.get("/logs/app", params={"limit": 20}).json()["lines"]
    assert any("Login falhou" in line for line in logs)


def test_anonimo_nao_le_logs(client):
    response = client.get("/logs/app")
    assert response.status_code == 401


def test_limit_e_respeitado(admin_client):
    response = admin_client.get("/logs/app", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()["lines"]) <= 2


# ---------- leitura do final do arquivo e rotação ----------

from src.core.logging_config import build_file_handler, read_log_tail  # noqa: E402
import logging  # noqa: E402


def write(path, text):
    path.write_bytes(text.encode("utf-8"))


def test_cauda_devolve_so_as_ultimas_linhas_em_ordem(tmp_path):
    arquivo = tmp_path / "app.log"
    write(arquivo, "".join(f"linha {i}\n" for i in range(1, 51)))
    assert read_log_tail(str(arquivo), 3) == ["linha 48", "linha 49", "linha 50"]


def test_cauda_com_menos_linhas_que_o_limite_devolve_tudo(tmp_path):
    arquivo = tmp_path / "app.log"
    write(arquivo, "a\nb\n")
    assert read_log_tail(str(arquivo), 100) == ["a", "b"]


def test_cauda_de_arquivo_vazio_ou_inexistente_e_lista_vazia(tmp_path):
    vazio = tmp_path / "vazio.log"
    vazio.write_bytes(b"")
    assert read_log_tail(str(vazio), 10) == []
    assert read_log_tail(str(tmp_path / "nao_existe.log"), 10) == []


def test_cauda_aceita_ultima_linha_sem_quebra_final(tmp_path):
    arquivo = tmp_path / "app.log"
    write(arquivo, "a\nb\nc")
    assert read_log_tail(str(arquivo), 2) == ["b", "c"]


def test_cauda_nao_quebra_caractere_de_varios_bytes_na_fronteira_do_bloco(tmp_path):
    arquivo = tmp_path / "app.log"
    linhas = [f"ação número {i} — conteúdo não-ASCII ✓" for i in range(200)]
    write(arquivo, "\n".join(linhas) + "\n")
    # blocos de 7 bytes caem no meio de caracteres de 2 e 3 bytes
    assert read_log_tail(str(arquivo), 25, block_size=7) == linhas[-25:]


def test_cauda_le_so_o_final_de_um_arquivo_grande(tmp_path, monkeypatch):
    arquivo = tmp_path / "app.log"
    write(arquivo, "".join(f"linha {i:07d}\n" for i in range(200_000)))  # ~3 MB
    lidos = []
    original = open

    def espiao(*args, **kwargs):
        f = original(*args, **kwargs)
        leitura = f.read
        f.read = lambda n=-1: (lidos.append(n), leitura(n))[1]
        return f

    monkeypatch.setattr("builtins.open", espiao)
    resultado = read_log_tail(str(arquivo), 5)
    assert resultado[-1] == "linha 0199999" and len(resultado) == 5
    assert sum(n for n in lidos if n > 0) < 100_000  # nada perto dos ~3 MB do arquivo


def test_log_gira_ao_passar_do_limite_e_descarta_os_mais_antigos(tmp_path):
    caminho = tmp_path / "giro.log"
    giro = logging.getLogger(f"teste.giro.{tmp_path.name}")
    giro.setLevel(logging.INFO)
    giro.propagate = False
    handler = build_file_handler(str(caminho), max_bytes=400, backup_count=2)
    giro.addHandler(handler)
    try:
        for i in range(60):
            giro.info("mensagem de teste número %03d", i)
    finally:
        handler.close()
        giro.removeHandler(handler)

    arquivos = sorted(p.name for p in tmp_path.iterdir())
    assert arquivos == ["giro.log", "giro.log.1", "giro.log.2"]  # nunca passa de 1 + 2 antigos
    assert all(p.stat().st_size <= 600 for p in tmp_path.iterdir())
    assert "059" in caminho.read_text(encoding="utf-8")  # o mais recente fica no arquivo atual


def test_aplicacao_usa_o_handler_com_rotacao():
    from logging.handlers import RotatingFileHandler

    from src.core.logging_config import LOG_BACKUP_COUNT, LOG_MAX_BYTES, logger, setup_logging

    setup_logging()
    rotativos = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert rotativos and rotativos[0].maxBytes == LOG_MAX_BYTES and rotativos[0].backupCount == LOG_BACKUP_COUNT
