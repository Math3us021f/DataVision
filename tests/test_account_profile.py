"""Minha conta: perfil (nome e cor do avatar), uso, acessos recentes e encerramento de outras sessões."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.core.db import get_connection
from src.main import app
from src.services.account import MAX_LOGIN_EVENTS, record_login_event, summarize_user_agent

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
PASSWORD = "senha-inicial-123"

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
EDGE_WIN = CHROME_WIN + " Edg/120.0"
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
SAFARI_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1"


def make_user(prefix="acc"):
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        created = admin.post("/users", json={"username": username, "password": PASSWORD}).json()
    client = TestClient(app)
    assert client.post("/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return client, username, created["id"]


@pytest.fixture
def user():
    client, username, user_id = make_user()
    with client:
        yield client, username, user_id


def test_perfil_traz_dados_basicos_e_uso_com_numeros_exatos(user):
    client, username, _ = user
    csv = b"a,b\n1,2\n3,4\n"
    dataset_id = client.post("/datasets/upload", files={"file": ("x.csv", io.BytesIO(csv), "text/csv")}).json()["id"]
    client.post(f"/datasets/{dataset_id}/profile")
    client.put(f"/datasets/{dataset_id}/dashboard", json={"widgets": [{"chart": "kpi", "metrics": [{"column": "a", "agg": "sum"}]}]})

    body = client.get("/me/profile").json()
    assert body["username"] == username
    assert body["is_admin"] is False
    assert body["display_name"] is None and body["avatar_color"] is None
    assert body["member_since"]
    assert body["usage"] == {"datasets": 1, "storage_bytes": len(csv), "profiled": 1, "dashboards": 1}


def test_salvar_perfil_aparece_no_perfil_e_em_me(user):
    client, _, _ = user
    saved = client.put("/me/profile", json={"display_name": "  Maria Souza  ", "avatar_color": "violet"})
    assert saved.status_code == 200
    assert saved.json()["display_name"] == "Maria Souza"  # sem espaços nas pontas

    assert client.get("/me/profile").json()["avatar_color"] == "violet"
    me = client.get("/me").json()
    assert me["display_name"] == "Maria Souza" and me["avatar_color"] == "violet"


def test_enviar_vazio_ou_nulo_limpa_nome_e_cor(user):
    client, _, _ = user
    client.put("/me/profile", json={"display_name": "Alguém", "avatar_color": "teal"})
    cleared = client.put("/me/profile", json={"display_name": "   ", "avatar_color": None}).json()
    assert cleared["display_name"] is None and cleared["avatar_color"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "x" * 61},
        {"display_name": "nome\x00com controle"},
        {"avatar_color": "vermelho-neon"},
        {"display_name": "ok", "admin": True},  # chave desconhecida
    ],
)
def test_perfil_invalido_retorna_422_e_nao_grava(user, payload):
    client, _, _ = user
    assert client.put("/me/profile", json=payload).status_code == 422
    assert client.get("/me/profile").json()["display_name"] is None


def test_nome_com_html_e_guardado_como_texto_literal(user):
    client, _, _ = user
    nome = "<img src=x onerror=alert(1)>"
    client.put("/me/profile", json={"display_name": nome})
    assert client.get("/me").json()["display_name"] == nome  # quem exibe escapa (React/Jinja)


def test_usuario_nao_altera_o_perfil_de_outro_nem_se_promove(user):
    client, _, _ = user
    client.put("/me/profile", json={"display_name": "Eu"})
    # o endpoint só opera sobre a própria conta e não aceita campos de privilégio
    assert client.put("/me/profile", json={"is_admin": True}).status_code == 422
    assert client.get("/me").json()["is_admin"] is False


def test_endpoints_exigem_login():
    with TestClient(app) as anon:
        assert anon.get("/me/profile").status_code == 401
        assert anon.put("/me/profile", json={}).status_code == 401
        assert anon.get("/me/logins").status_code == 401
        assert anon.post("/me/sessions/revoke-others").status_code == 401


# ---------- Acessos recentes ----------

def test_login_e_falha_viram_eventos_do_mais_novo_para_o_mais_antigo():
    client, username, _ = make_user()
    with client:
        with TestClient(app) as other:
            other.post("/login", json={"username": username, "password": "errada-123"}, headers={"user-agent": FIREFOX_LINUX})
            other.post("/login", json={"username": username, "password": PASSWORD}, headers={"user-agent": CHROME_WIN})

        eventos = client.get("/me/logins").json()
        assert [(e["success"], e["browser"]) for e in eventos[:3]] == [
            (True, "Chrome · Windows"),
            (False, "Firefox · Linux"),
            (True, "Outro navegador · sistema desconhecido"),  # login do make_user (User-Agent do TestClient)
        ]


def test_conta_inativa_tentando_entrar_registra_falha():
    client, username, user_id = make_user()
    with client:
        with TestClient(app) as admin:
            admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
            admin.patch(f"/users/{user_id}", json={"is_active": False})
        with TestClient(app) as other:
            assert other.post("/login", json={"username": username, "password": PASSWORD}).status_code == 401
    with get_connection() as conn:
        falhas = conn.execute("SELECT COUNT(*) AS n FROM login_events WHERE user_id = %s AND NOT success", (user_id,)).fetchone()["n"]
    assert falhas == 1


def test_usuario_so_ve_os_proprios_acessos():
    a, _, _ = make_user()
    b, _, b_id = make_user()
    with a, b:
        assert len(b.get("/me/logins").json()) == 1
        with get_connection() as conn:
            total_b = conn.execute("SELECT COUNT(*) AS n FROM login_events WHERE user_id = %s", (b_id,)).fetchone()["n"]
        assert total_b == 1  # o login de `a` não entrou na conta de `b`


def test_login_de_usuario_inexistente_nao_cria_evento():
    with get_connection() as conn:
        antes = conn.execute("SELECT COUNT(*) AS n FROM login_events").fetchone()["n"]
    with TestClient(app) as anon:
        assert anon.post("/login", json={"username": f"nao_existe_{uuid.uuid4().hex[:8]}", "password": "qualquer-senha"}).status_code == 401
    with get_connection() as conn:
        depois = conn.execute("SELECT COUNT(*) AS n FROM login_events").fetchone()["n"]
    assert depois == antes


def test_privacidade_tabela_nao_guarda_ip_nem_texto_do_navegador():
    with get_connection() as conn:
        colunas = {r["column_name"] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'login_events'"
        ).fetchall()}
    assert colunas == {"id", "user_id", "success", "browser", "created_at"}


def test_retencao_guarda_so_os_mais_recentes(user):
    _, _, user_id = user
    with get_connection() as conn:
        for _ in range(MAX_LOGIN_EVENTS + 5):
            record_login_event(conn, user_id, True, CHROME_WIN)
        conn.commit()
        total = conn.execute("SELECT COUNT(*) AS n FROM login_events WHERE user_id = %s", (user_id,)).fetchone()["n"]
    assert total == MAX_LOGIN_EVENTS


@pytest.mark.parametrize(
    "ua, esperado",
    [
        (CHROME_WIN, "Chrome · Windows"),
        (EDGE_WIN, "Edge · Windows"),
        (FIREFOX_LINUX, "Firefox · Linux"),
        (SAFARI_IPHONE, "Safari · iOS"),
        ("", "Desconhecido"),
        (None, "Desconhecido"),
        ("curl/8.0", "Outro navegador · sistema desconhecido"),
    ],
)
def test_resumo_do_navegador(ua, esperado):
    assert summarize_user_agent(ua) == esperado


def test_excluir_o_usuario_apaga_os_acessos_dele():
    client, _, user_id = make_user()
    with client:
        pass
    with TestClient(app) as admin:
        admin.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        assert admin.delete(f"/users/{user_id}").status_code == 204
    with get_connection() as conn:
        restantes = conn.execute("SELECT COUNT(*) AS n FROM login_events WHERE user_id = %s", (user_id,)).fetchone()["n"]
    assert restantes == 0


# ---------- Encerrar outras sessões ----------

def test_encerrar_outras_sessoes_derruba_as_demais_e_mantem_a_atual():
    atual, username, user_id = make_user()
    with atual:
        outra = TestClient(app)
        outra.post("/login", json={"username": username, "password": PASSWORD})
        assert outra.get("/me").status_code == 200

        assert atual.post("/me/sessions/revoke-others").status_code == 204

        assert atual.get("/me").status_code == 200  # a sessão atual recebeu cookie novo
        assert outra.get("/me").status_code == 401  # as outras caíram
        outra.close()

    with get_connection() as conn:
        registro = conn.execute(
            "SELECT action FROM audit_logs WHERE actor_user_id = %s ORDER BY id DESC LIMIT 1", (user_id,)
        ).fetchone()
    assert registro["action"] == "revoke_other_sessions"
