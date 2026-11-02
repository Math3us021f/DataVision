"""Exclusão de dataset e exclusão forçada de usuário (usuário + datasets + MinIO)."""

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from minio import Minio

from src.db import get_connection
from src.main import app

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture
def admin_client():
    with TestClient(app) as c:
        c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        yield c


def create_user(admin_client):
    username = f"fdel_{uuid.uuid4().hex[:8]}"
    admin_client.post("/users", json={"username": username, "password": "senha-123-x"})
    client = TestClient(app)
    client.post("/login", json={"username": username, "password": "senha-123-x"})
    return client, username


def upload(client, name="dados.csv", content=b"a,b\n1,2\n"):
    return client.post("/datasets/upload", files={"file": (name, io.BytesIO(content), "text/csv")}).json()


def minio_client():
    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=False,
    )


def object_exists(object_key):
    try:
        minio_client().stat_object(os.environ["MINIO_BUCKET"], object_key)
        return True
    except Exception:
        return False


# ---------- DELETE /datasets/{id} ----------

def test_dono_exclui_proprio_dataset(admin_client):
    client, _ = create_user(admin_client)

    dataset = upload(client)
    object_key = None
    with get_connection() as conn:
        object_key = conn.execute("SELECT object_key FROM datasets WHERE id=%s", (dataset["id"],)).fetchone()["object_key"]
    assert object_exists(object_key)

    response = client.delete(f"/datasets/{dataset['id']}")
    assert response.status_code == 204
    assert client.get("/datasets").json() == []
    assert not object_exists(object_key)


def test_nao_pode_excluir_dataset_de_outro(admin_client):
    owner, _ = create_user(admin_client)
    dataset = upload(owner)

    other, _ = create_user(admin_client)
    response = other.delete(f"/datasets/{dataset['id']}")
    assert response.status_code == 404


def test_excluir_dataset_inexistente_e_404(admin_client):
    user, _ = create_user(admin_client)
    assert user.delete("/datasets/999999999").status_code == 404


def test_excluir_dataset_sem_login_e_401():
    with TestClient(app) as anon:
        assert anon.delete("/datasets/1").status_code == 401


def test_perfil_some_junto_com_o_dataset(admin_client):
    user, _ = create_user(admin_client)
    dataset = upload(user)
    user.post(f"/datasets/{dataset['id']}/profile")

    user.delete(f"/datasets/{dataset['id']}")

    with get_connection() as conn:
        profile = conn.execute("SELECT id FROM dataset_profiles WHERE dataset_id=%s", (dataset["id"],)).fetchone()
        columns = conn.execute("SELECT id FROM dataset_columns WHERE dataset_id=%s", (dataset["id"],)).fetchall()
    assert profile is None
    assert columns == []


# ---------- DELETE /users/{id}?force=true ----------

def test_excluir_sem_force_continua_bloqueado_com_dataset(admin_client):
    user, username = create_user(admin_client)
    created = admin_client.get("/users", params={"search": username}).json()["items"][0]
    upload(user)

    response = admin_client.delete(f"/users/{created['id']}")
    assert response.status_code == 409
    assert str(1) in response.json()["detail"]


def test_force_true_exclui_usuario_e_datasets(admin_client):
    user, username = create_user(admin_client)
    created = admin_client.get("/users", params={"search": username}).json()["items"][0]
    dataset = upload(user)
    with get_connection() as conn:
        object_key = conn.execute("SELECT object_key FROM datasets WHERE id=%s", (dataset["id"],)).fetchone()["object_key"]

    response = admin_client.delete(f"/users/{created['id']}", params={"force": "true"})
    assert response.status_code == 204

    assert admin_client.get("/users", params={"search": username}).json()["total"] == 0
    with get_connection() as conn:
        assert conn.execute("SELECT id FROM datasets WHERE id=%s", (dataset["id"],)).fetchone() is None
    assert not object_exists(object_key)


def test_force_true_registra_na_auditoria(admin_client):
    user, username = create_user(admin_client)
    created = admin_client.get("/users", params={"search": username}).json()["items"][0]
    upload(user)
    upload(user, "segundo.csv")

    admin_client.delete(f"/users/{created['id']}", params={"force": "true"})

    with get_connection() as conn:
        row = conn.execute(
            "SELECT details FROM audit_logs WHERE action='force_delete_user_datasets' AND target_user_id IS NULL "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    # target_user_id vira NULL após o usuário ser apagado (ON DELETE SET NULL); confirmamos pelo texto gravado antes.
    assert row is not None
    assert "2 dataset" in row["details"]


def test_force_true_sem_datasets_funciona_normalmente(admin_client):
    user, username = create_user(admin_client)
    created = admin_client.get("/users", params={"search": username}).json()["items"][0]

    response = admin_client.delete(f"/users/{created['id']}", params={"force": "true"})
    assert response.status_code == 204


def test_force_true_na_propria_conta_continua_bloqueado(admin_client):
    me = admin_client.get("/me").json()
    page = admin_client.get("/users", params={"search": me["username"]}).json()
    my_id = next(u["id"] for u in page["items"] if u["username"] == me["username"])

    response = admin_client.delete(f"/users/{my_id}", params={"force": "true"})
    assert response.status_code == 400


def test_force_true_so_admin(admin_client):
    owner, owner_username = create_user(admin_client)
    owner_id = admin_client.get("/users", params={"search": owner_username}).json()["items"][0]["id"]
    non_admin, _ = create_user(admin_client)

    response = non_admin.delete(f"/users/{owner_id}", params={"force": "true"})
    assert response.status_code == 403
