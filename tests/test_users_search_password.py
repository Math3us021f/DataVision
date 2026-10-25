"""Busca/paginação de usuários e troca/redefinição de senha."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def admin_client():
    with TestClient(app) as c:
        c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        yield c


def create_user(admin_client, prefix="busca", password="senha-inicial-1"):
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    created = admin_client.post("/users", json={"username": username, "password": password}).json()
    return created, password


def login(username, password):
    client = TestClient(app)
    response = client.post("/login", json={"username": username, "password": password})
    return client, response


# ---------- Busca, filtro e paginação ----------

def test_busca_por_parte_do_nome(admin_client):
    marker = uuid.uuid4().hex[:6]
    for _ in range(3):
        admin_client.post("/users", json={"username": f"zz{marker}_{uuid.uuid4().hex[:4]}", "password": "senha-123-x"})

    body = admin_client.get("/users", params={"search": marker}).json()
    assert body["total"] == 3
    assert all(marker in u["username"] for u in body["items"])


def test_busca_trata_curinga_como_texto(admin_client):
    # "%" sozinho, se fosse curinga do LIKE, casaria com todos os usuários.
    body = admin_client.get("/users", params={"search": "%"}).json()
    assert body["total"] == 0


def test_filtro_por_status(admin_client):
    created, _ = create_user(admin_client, prefix="statusf")
    admin_client.patch(f"/users/{created['id']}", json={"is_active": False})

    inativos = admin_client.get("/users", params={"search": created["username"], "status": "inactive"}).json()
    ativos = admin_client.get("/users", params={"search": created["username"], "status": "active"}).json()
    assert inativos["total"] == 1
    assert ativos["total"] == 0


def test_paginacao_respeita_page_size(admin_client):
    marker = uuid.uuid4().hex[:6]
    for _ in range(5):
        admin_client.post("/users", json={"username": f"pg{marker}_{uuid.uuid4().hex[:4]}", "password": "senha-123-x"})

    page1 = admin_client.get("/users", params={"search": marker, "page_size": 2, "page": 1}).json()
    page3 = admin_client.get("/users", params={"search": marker, "page_size": 2, "page": 3}).json()

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page3["items"]) == 1
    assert {u["id"] for u in page1["items"]}.isdisjoint({u["id"] for u in page3["items"]})


def test_page_size_maximo_e_validado(admin_client):
    response = admin_client.get("/users", params={"page_size": 1000})
    assert response.status_code == 422


# ---------- Senha mínima ----------

def test_criar_usuario_com_senha_curta_e_rejeitado(admin_client):
    response = admin_client.post("/users", json={"username": f"curta_{uuid.uuid4().hex[:6]}", "password": "1234567"})
    assert response.status_code == 400


# ---------- Admin redefine senha ----------

def test_admin_redefine_senha(admin_client):
    created, old_password = create_user(admin_client)

    response = admin_client.put(f"/users/{created['id']}/password", json={"new_password": "nova-senha-ok"})
    assert response.status_code == 204

    _, old_login = login(created["username"], old_password)
    _, new_login = login(created["username"], "nova-senha-ok")
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_redefinir_senha_encerra_sessoes_abertas(admin_client):
    created, password = create_user(admin_client)
    user_client, _ = login(created["username"], password)
    assert user_client.get("/me").status_code == 200

    admin_client.put(f"/users/{created['id']}/password", json={"new_password": "nova-senha-ok"})

    assert user_client.get("/me").status_code == 401


def test_redefinir_senha_curta_e_rejeitado(admin_client):
    created, _ = create_user(admin_client)
    response = admin_client.put(f"/users/{created['id']}/password", json={"new_password": "curta"})
    assert response.status_code == 400


def test_nao_admin_nao_redefine_senha(admin_client):
    created, password = create_user(admin_client)
    other, _ = create_user(admin_client)
    user_client, _ = login(created["username"], password)

    response = user_client.put(f"/users/{other['id']}/password", json={"new_password": "nova-senha-ok"})
    assert response.status_code == 403


def test_redefinicao_fica_na_auditoria(admin_client):
    from src.db import get_connection

    created, _ = create_user(admin_client)
    admin_client.put(f"/users/{created['id']}/password", json={"new_password": "nova-senha-ok"})

    with get_connection() as conn:
        row = conn.execute(
            "SELECT action FROM audit_logs WHERE target_user_id = %s ORDER BY id DESC LIMIT 1",
            (created["id"],),
        ).fetchone()
    assert row["action"] == "reset_password"


# ---------- Usuário troca a própria senha ----------

def test_trocar_propria_senha(admin_client):
    created, password = create_user(admin_client)
    user_client, _ = login(created["username"], password)

    response = user_client.put("/me/password", json={"current_password": password, "new_password": "minha-nova-1"})
    assert response.status_code == 204

    # A sessão atual continua válida (recebeu cookie novo)...
    assert user_client.get("/me").status_code == 200
    # ...e a nova senha funciona.
    _, new_login = login(created["username"], "minha-nova-1")
    assert new_login.status_code == 200


def test_trocar_propria_senha_encerra_outras_sessoes(admin_client):
    created, password = create_user(admin_client)
    session_a, _ = login(created["username"], password)
    session_b, _ = login(created["username"], password)

    session_a.put("/me/password", json={"current_password": password, "new_password": "minha-nova-1"})

    assert session_a.get("/me").status_code == 200
    assert session_b.get("/me").status_code == 401


def test_trocar_propria_senha_exige_senha_atual_correta(admin_client):
    created, password = create_user(admin_client)
    user_client, _ = login(created["username"], password)

    response = user_client.put("/me/password", json={"current_password": "errada-123", "new_password": "minha-nova-1"})
    assert response.status_code == 400

    _, still_old = login(created["username"], password)
    assert still_old.status_code == 200


def test_trocar_propria_senha_sem_login_e_401():
    with TestClient(app) as anon:
        response = anon.put("/me/password", json={"current_password": "x", "new_password": "minha-nova-1"})
    assert response.status_code == 401
