"""Gestão de usuários (só administradores): criar, listar, buscar, ativar, excluir, senha e e-mail."""

import pytest
from django.contrib.auth import get_user_model

from audit.models import AuditLog
from datasets.models import Dashboard, Dataset, DatasetColumn, DatasetProfile
from tests.conftest import PASSWORD, ApiClient, logged_client, make_user

User = get_user_model()
pytestmark = pytest.mark.django_db


def criar(cliente, username="novo", **extra):
    return cliente.post("/users", json={"username": username, "password": PASSWORD, **extra})


def acoes(**filtros):
    return list(AuditLog.objects.filter(**filtros).order_by("id").values_list("action", flat=True))


# ---------- permissões ----------


@pytest.mark.parametrize("metodo, caminho", [("get", "/users"), ("get", "/users/summary"), ("post", "/users"), ("patch", "/users/1"), ("delete", "/users/1"), ("put", "/users/1/password"), ("patch", "/users/1/email")])
def test_anonimo_recebe_401_e_usuario_comum_403(common_client, metodo, caminho):
    corpo = {"json": {}} if metodo in ("post", "patch", "put") else {}
    assert getattr(ApiClient(), metodo)(caminho, **corpo).status_code == 401
    resposta = getattr(common_client, metodo)(caminho, **corpo)
    assert resposta.status_code == 403 and resposta.json()["detail"] == "Requer privilégio de administrador"


def test_acoes_de_admin_exigem_o_token_csrf(admin):
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.force_login(admin)
    assert cliente.get("/users").status_code == 200  # leitura não precisa de token
    assert cliente.post("/users", json={"username": "x", "password": PASSWORD}).status_code == 403
    assert cliente.patch("/users/1", json={"is_active": False}).status_code == 403
    assert not User.objects.filter(username="x").exists()


# ---------- criar ----------


def test_admin_cria_usuario_e_a_senha_e_guardada_com_hash(admin_client):
    resposta = criar(admin_client)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["username"] == "novo" and corpo["is_admin"] is False and corpo["is_active"] is True and corpo["email_masked"] is None
    assert User.objects.get(username="novo").check_password(PASSWORD)
    assert "password" not in resposta.content.decode()
    assert acoes(target__username="novo") == ["create_user"]


def test_criar_com_email_devolve_so_a_versao_mascarada(admin_client):
    resposta = criar(admin_client, email="Maria.Souza@Exemplo.com")
    assert resposta.json()["email_masked"] == "m***@exemplo.com"
    assert User.objects.get(username="novo").email == "maria.souza@exemplo.com"  # normalizado
    assert "maria.souza" not in resposta.content.decode()
    assert AuditLog.objects.get(action="create_user").details == "com e-mail m***@exemplo.com"


@pytest.mark.parametrize(
    "dados, status, trecho",
    [
        ({"username": "   "}, 400, "Informe o nome de usuário"),
        ({"username": "x" * 151}, 400, "no máximo 150"),
        ({"password": "curta"}, 400, "pelo menos 8"),
        ({"password": "ç" * 40}, 400, "no máximo 72 bytes"),
        ({"email": "isso-nao-e-email"}, 400, "e-mail válido"),
    ],
)
def test_criar_valida_a_entrada(admin_client, dados, status, trecho):
    base = {"username": "novo", "password": PASSWORD}
    resposta = admin_client.post("/users", json={**base, **dados})
    assert resposta.status_code == status and trecho in resposta.json()["detail"]
    assert not User.objects.filter(username="novo").exists()


def test_criar_repetido_da_409_para_usuario_e_para_email(admin_client):
    criar(admin_client, "a", email="a@exemplo.com")
    assert criar(admin_client, "a").status_code == 409
    assert criar(admin_client, "b", email="A@EXEMPLO.COM").status_code == 409  # sem diferenciar maiúsculas


def test_campos_a_mais_no_corpo_sao_ignorados_e_tipos_errados_dao_422(admin_client):
    assert admin_client.post("/users", json={"username": "u", "password": PASSWORD, "is_admin": "talvez"}).status_code == 422
    assert admin_client.post("/users", json={"username": "u"}).status_code == 422  # falta a senha


# ---------- listar, buscar, resumo ----------


def test_lista_pagina_busca_e_filtra(admin_client, admin):
    for i in range(25):
        make_user(f"lista{i:02d}")
    make_user("especial%_1")
    make_user("inativo1", is_active=False)

    p1 = admin_client.get("/users", {"search": "lista", "page_size": 10}).json()
    assert p1["total"] == 25 and len(p1["items"]) == 10 and p1["page"] == 1 and p1["page_size"] == 10
    ultima = admin_client.get("/users", {"search": "lista", "page_size": 10, "page": 3}).json()
    assert [u["username"] for u in ultima["items"]] == [f"lista{i:02d}" for i in range(20, 25)]

    assert [u["username"] for u in admin_client.get("/users", {"search": "%_"}).json()["items"]] == ["especial%_1"]  # curinga é literal
    assert admin_client.get("/users", {"search": "LISTA00"}).json()["total"] == 1  # sem diferenciar maiúsculas
    inativos = admin_client.get("/users", {"status": "inactive"}).json()
    assert [u["username"] for u in inativos["items"]] == ["inativo1"]
    assert admin_client.get("/users", {"status": "active"}).json()["total"] == User.objects.filter(is_active=True).count()


def test_lista_mostra_o_email_mascarado_e_nunca_o_inteiro(admin_client):
    make_user("com_email", email="zelia@exemplo.com")
    resposta = admin_client.get("/users", {"search": "com_email"})
    assert resposta.json()["items"][0]["email_masked"] == "z***@exemplo.com" and "zelia@" not in resposta.content.decode()


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"status": "talvez"}, {"search": "x" * 101}])
def test_lista_rejeita_parametros_invalidos(admin_client, params):
    assert admin_client.get("/users", params).status_code == 422


def test_resumo_de_contas(admin_client):
    antes = admin_client.get("/users/summary").json()
    assert antes["total"] == antes["active"] + antes["inactive"]
    make_user("a")
    make_user("b", is_active=False)
    make_user("c", is_admin=True)
    depois = admin_client.get("/users/summary").json()
    assert depois == {"total": antes["total"] + 3, "active": antes["active"] + 2, "inactive": antes["inactive"] + 1, "admins": antes["admins"] + 1}


# ---------- ativar e desativar ----------


def test_desativar_e_reativar_registra_na_auditoria(admin_client):
    alvo = make_user("alvo")
    off = admin_client.patch(f"/users/{alvo.pk}", json={"is_active": False})
    assert off.status_code == 200 and off.json()["is_active"] is False
    on = admin_client.patch(f"/users/{alvo.pk}", json={"is_active": True})
    assert on.json()["is_active"] is True
    assert acoes(target=alvo) == ["deactivate_user", "activate_user"]


def test_desativar_derruba_a_sessao_do_usuario(admin_client):
    alvo = make_user("alvo")
    cliente = logged_client(alvo)
    assert cliente.get("/me").status_code == 200
    admin_client.patch(f"/users/{alvo.pk}", json={"is_active": False})
    assert cliente.get("/me").status_code == 401


def test_admin_nao_desativa_a_propria_conta_e_usuario_inexistente_da_404(admin_client, admin):
    assert admin_client.patch(f"/users/{admin.pk}", json={"is_active": False}).status_code == 400
    assert admin_client.patch("/users/99999999", json={"is_active": False}).status_code == 404
    assert admin_client.patch("/users/abc", json={"is_active": False}).status_code == 404  # só números casam com a rota


# ---------- excluir ----------


def test_excluir_remove_a_conta_e_a_auditoria_permanece(admin_client, admin):
    alvo = make_user("alvo")
    antes = AuditLog.objects.count()
    assert admin_client.delete(f"/users/{alvo.pk}").status_code == 204
    assert not User.objects.filter(pk=alvo.pk).exists()
    registro = AuditLog.objects.order_by("-id").first()
    assert registro.action == "delete_user" and registro.actor == admin and registro.target is None
    assert registro.details == f"id={alvo.pk} username='alvo'" and AuditLog.objects.count() == antes + 1


def test_excluir_a_si_mesmo_ou_inexistente(admin_client, admin):
    assert admin_client.delete(f"/users/{admin.pk}").status_code == 400
    assert admin_client.delete("/users/99999999").status_code == 404


def test_usuario_com_datasets_so_e_excluido_com_force_e_apaga_os_arquivos(admin_client, fake_minio):
    alvo = make_user("alvo")
    dataset = Dataset.objects.create(owner=alvo, original_name="d.csv", object_key="chave1.csv", format=".csv", size_bytes=10)
    DatasetProfile.objects.create(dataset=dataset, row_count=1, duplicate_row_count=0)
    DatasetColumn.objects.create(dataset=dataset, column_name="a", inferred_type="integer", null_count=0, distinct_count=1)
    Dashboard.objects.create(dataset=dataset, owner=alvo, spec={})

    bloqueado = admin_client.delete(f"/users/{alvo.pk}")
    assert bloqueado.status_code == 409 and "1 dataset(s)" in bloqueado.json()["detail"]
    assert User.objects.filter(pk=alvo.pk).exists() and Dataset.objects.filter(pk=dataset.pk).exists() and fake_minio == []

    assert admin_client.delete(f"/users/{alvo.pk}?force=true").status_code == 204
    assert not User.objects.filter(pk=alvo.pk).exists() and not Dataset.objects.exists()
    assert not DatasetProfile.objects.exists() and not DatasetColumn.objects.exists() and not Dashboard.objects.exists()
    assert fake_minio == [("bucket-de-teste", "chave1.csv")]  # o arquivo no MinIO foi removido
    assert acoes(details__contains="alvo") == ["delete_user"] and "force_delete_user_datasets" in acoes()


def test_falha_no_minio_nao_trava_a_exclusao(admin_client, monkeypatch):
    alvo = make_user("alvo")
    Dataset.objects.create(owner=alvo, original_name="d.csv", object_key="chave2.csv", format=".csv", size_bytes=1)

    class Quebrado:
        def remove_object(self, *args):
            raise OSError("MinIO fora do ar")

    monkeypatch.setenv("MINIO_BUCKET", "b")
    monkeypatch.setattr("core.storage.get_minio_client", lambda: Quebrado())
    assert admin_client.delete(f"/users/{alvo.pk}?force=true").status_code == 204  # fica um objeto órfão, não um usuário preso
    assert not User.objects.filter(pk=alvo.pk).exists()


# ---------- redefinir senha ----------


def test_redefinir_senha_derruba_as_sessoes_e_a_nova_funciona(admin_client):
    alvo = make_user("alvo")
    sessao = logged_client(alvo)
    assert admin_client.put(f"/users/{alvo.pk}/password", json={"new_password": "nova-senha-9"}).status_code == 204
    assert sessao.get("/me").status_code == 401  # a sessão antiga caiu
    assert ApiClient().post("/login", json={"username": "alvo", "password": "nova-senha-9"}).status_code == 200
    assert ApiClient().post("/login", json={"username": "alvo", "password": PASSWORD}).status_code == 401
    assert acoes(target=alvo) == ["reset_password"]


def test_redefinir_valida_a_senha_e_o_usuario(admin_client):
    alvo = make_user("alvo")
    assert admin_client.put(f"/users/{alvo.pk}/password", json={"new_password": "curta"}).status_code == 400
    assert admin_client.put("/users/99999999/password", json={"new_password": "nova-senha-9"}).status_code == 404
    assert User.objects.get(pk=alvo.pk).check_password(PASSWORD)  # nada mudou


# ---------- e-mail alterado pelo administrador ----------


def test_admin_define_o_email_pessoa_e_avisada_e_a_auditoria_registra(admin_client, outbox):
    alvo = make_user("alvo")
    resposta = admin_client.patch(f"/users/{alvo.pk}/email", json={"email": "Nova@Exemplo.com"})
    assert resposta.status_code == 200 and resposta.json()["email_masked"] == "n***@exemplo.com"
    assert outbox == []  # sem confirmação por e-mail quando é o admin

    avisos = logged_client(alvo).get("/me/notifications").json()
    assert avisos["unread"] == 1 and "n***@exemplo.com" in avisos["items"][0]["message"] and "nova@" not in str(avisos)
    registro = AuditLog.objects.get(action="admin_change_email")
    assert registro.details == "sem e-mail → n***@exemplo.com" and "nova@" not in registro.details


def test_admin_remove_o_email_e_o_login_volta_a_pedir_so_a_senha(admin_client, outbox):
    alvo = make_user("alvo", email="alvo@exemplo.com")
    assert admin_client.patch(f"/users/{alvo.pk}/email", json={"email": None}).json()["email_masked"] is None
    assert ApiClient().post("/login", json={"username": "alvo", "password": PASSWORD}).json() == {"status": "ok"}
    cliente = logged_client(alvo)
    assert "removeu" in cliente.get("/me/notifications").json()["items"][0]["message"]


def test_trocar_o_email_descarta_codigos_pendentes_do_antigo(admin_client, outbox):
    from tests.conftest import code_of

    alvo = make_user("alvo", email="alvo@exemplo.com")
    cliente = ApiClient()
    cliente.post("/login", json={"username": "alvo", "password": PASSWORD})
    antigo = code_of(outbox[0])
    admin_client.patch(f"/users/{alvo.pk}/email", json={"email": "outro@exemplo.com"})
    assert cliente.post("/login/verify", json={"code": antigo}).status_code == 401


def test_admin_nao_altera_o_proprio_email_por_aqui(admin_client, admin):
    resposta = admin_client.patch(f"/users/{admin.pk}/email", json={"email": "eu@exemplo.com"})
    assert resposta.status_code == 400 and "Minha conta" in resposta.json()["detail"]


def test_email_do_admin_valida_formato_existencia_e_duplicado(admin_client):
    alvo = make_user("alvo")
    make_user("outro", email="outro@exemplo.com")
    assert admin_client.patch(f"/users/{alvo.pk}/email", json={"email": "invalido"}).status_code == 400
    assert admin_client.patch("/users/99999999/email", json={"email": "a@exemplo.com"}).status_code == 404
    assert admin_client.patch(f"/users/{alvo.pk}/email", json={"email": "OUTRO@exemplo.com"}).status_code == 409
    assert not User.objects.get(pk=alvo.pk).email
