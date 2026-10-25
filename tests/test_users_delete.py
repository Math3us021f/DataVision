"""Exclusão de usuários."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.db import get_connection
from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def admin_client():
    with TestClient(app) as c:
        c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        yield c


def create_user(admin_client, is_admin=False):
    username = f"del_{uuid.uuid4().hex[:8]}"
    created = admin_client.post(
        "/users", json={"username": username, "password": "senha-123-x", "is_admin": is_admin}
    ).json()
    return created


def login(username, password="senha-123-x"):
    client = TestClient(app)
    client.post("/login", json={"username": username, "password": password})
    return client


def test_admin_exclui_usuario(admin_client):
    user = create_user(admin_client)

    response = admin_client.delete(f"/users/{user['id']}")
    assert response.status_code == 204

    assert admin_client.get("/users", params={"search": user["username"]}).json()["total"] == 0
    assert TestClient(app).post(
        "/login", json={"username": user["username"], "password": "senha-123-x"}
    ).status_code == 401


def test_excluir_encerra_sessao_aberta(admin_client):
    user = create_user(admin_client)
    user_client = login(user["username"])
    assert user_client.get("/me").status_code == 200

    admin_client.delete(f"/users/{user['id']}")

    assert user_client.get("/me").status_code == 401


def test_admin_nao_exclui_a_propria_conta(admin_client):
    me = admin_client.get("/me").json()
    page = admin_client.get("/users", params={"search": me["username"]}).json()
    my_id = next(u["id"] for u in page["items"] if u["username"] == me["username"])

    assert admin_client.delete(f"/users/{my_id}").status_code == 400


def test_excluir_inexistente_retorna_404(admin_client):
    assert admin_client.delete("/users/999999999").status_code == 404


def test_nao_admin_nao_exclui(admin_client):
    target = create_user(admin_client)
    user = create_user(admin_client)
    user_client = login(user["username"])

    assert user_client.delete(f"/users/{target['id']}").status_code == 403


def test_anonimo_nao_exclui(admin_client):
    target = create_user(admin_client)
    with TestClient(app) as anon:
        assert anon.delete(f"/users/{target['id']}").status_code == 401


def test_usuario_com_dataset_nao_pode_ser_excluido(admin_client):
    user = create_user(admin_client)
    user_client = login(user["username"])
    upload = user_client.post(
        "/datasets/upload", files={"file": ("dados.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}
    )
    assert upload.status_code == 201

    response = admin_client.delete(f"/users/{user['id']}")
    assert response.status_code == 409
    assert admin_client.get("/users", params={"search": user["username"]}).json()["total"] == 1


def test_auditoria_e_preservada_apos_excluir(admin_client):
    # Um admin secundário gera auditoria como ATOR e é alvo de outra ação; depois é excluído.
    second_admin = create_user(admin_client, is_admin=True)
    second_client = login(second_admin["username"])
    created_by_second = create_user(second_client)

    with get_connection() as conn:
        before = conn.execute(
            "SELECT id FROM audit_logs WHERE action = 'create_user' AND target_user_id = %s",
            (created_by_second["id"],),
        ).fetchone()

    assert admin_client.delete(f"/users/{second_admin['id']}").status_code == 204

    with get_connection() as conn:
        still_there = conn.execute(
            "SELECT actor_user_id FROM audit_logs WHERE id = %s", (before["id"],)
        ).fetchone()
        deletion = conn.execute(
            "SELECT details FROM audit_logs WHERE action = 'delete_user' AND details LIKE %s",
            (f"%{second_admin['username']}%",),
        ).fetchone()

    assert still_there is not None
    assert still_there["actor_user_id"] is None
    assert deletion is not None
