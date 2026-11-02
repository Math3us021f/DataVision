"""Histórico de auditoria (só administradores): busca, filtro por ação e paginação."""

import pytest
from django.contrib.auth import get_user_model

from audit.models import AuditLog
from tests.conftest import ApiClient, make_user

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def historico(admin):
    ana, beto = make_user("ana"), make_user("beto")
    AuditLog.objects.create(actor=admin, action="create_user", target=ana)
    AuditLog.objects.create(actor=admin, action="deactivate_user", target=ana, details="motivo qualquer")
    AuditLog.objects.create(actor=admin, action="create_user", target=beto)
    AuditLog.objects.create(actor=ana, action="change_own_password", target=ana)
    return ana, beto


@pytest.mark.parametrize("caminho", ["/audit-logs", "/audit-logs/actions"])
def test_so_administrador_ve_a_auditoria(common_client, caminho):
    assert ApiClient().get(caminho).status_code == 401
    assert common_client.get(caminho).status_code == 403


def test_lista_do_mais_recente_para_o_mais_antigo_com_nomes(admin_client, historico):
    corpo = admin_client.get("/audit-logs").json()
    assert corpo["total"] == 4 and corpo["page"] == 1 and corpo["page_size"] == 20
    assert [i["action"] for i in corpo["items"]] == ["change_own_password", "create_user", "deactivate_user", "create_user"]
    primeiro = corpo["items"][0]
    assert primeiro["actor_username"] == "ana" and primeiro["target_username"] == "ana" and primeiro["details"] is None
    assert corpo["items"][2]["details"] == "motivo qualquer"
    assert set(primeiro) == {"id", "action", "details", "created_at", "actor_username", "target_username"}


def test_busca_por_quem_fez_ou_quem_sofreu_a_acao(admin_client, historico):
    assert admin_client.get("/audit-logs", {"search": "beto"}).json()["total"] == 1  # só como alvo
    assert admin_client.get("/audit-logs", {"search": "chefe"}).json()["total"] == 3  # só como autor
    assert admin_client.get("/audit-logs", {"search": "ANA"}).json()["total"] == 3  # sem diferenciar maiúsculas; o registro em que ela é autora E alvo conta uma vez
    assert admin_client.get("/audit-logs", {"search": "nao-existe"}).json()["items"] == []


def test_busca_trata_curingas_como_texto(admin_client, historico):
    make_user("a_b")
    AuditLog.objects.create(actor=User.objects.get(username="a_b"), action="reset_password")
    assert admin_client.get("/audit-logs", {"search": "a_b"}).json()["total"] == 1  # "_" não casa qualquer letra
    assert admin_client.get("/audit-logs", {"search": "%"}).json()["total"] == 0


def test_filtro_por_acao_e_paginacao(admin_client, historico):
    assert admin_client.get("/audit-logs", {"action": "create_user"}).json()["total"] == 2
    pagina = admin_client.get("/audit-logs", {"page_size": 3, "page": 2}).json()
    assert pagina["total"] == 4 and len(pagina["items"]) == 1
    combinado = admin_client.get("/audit-logs", {"action": "create_user", "search": "beto"}).json()
    assert combinado["total"] == 1


@pytest.mark.parametrize("params", [{"action": "acao_inventada"}, {"page": 0}, {"page_size": 101}, {"search": "x" * 101}])
def test_parametros_invalidos_dao_422(admin_client, params):
    assert admin_client.get("/audit-logs", params).status_code == 422


def test_lista_de_acoes_conhecidas(admin_client):
    acoes = admin_client.get("/audit-logs/actions").json()
    assert acoes == [
        "create_user", "activate_user", "deactivate_user", "delete_user", "force_delete_user_datasets",
        "reset_password", "change_own_password", "revoke_other_sessions", "change_own_email", "admin_change_email",
    ]


def test_registro_sobrevive_a_exclusao_do_usuario(admin_client, admin):
    alvo = make_user("temporario")
    admin_client.delete(f"/users/{alvo.pk}")
    item = admin_client.get("/audit-logs", {"action": "delete_user"}).json()["items"][0]
    assert item["target_username"] is None and "temporario" in item["details"] and item["actor_username"] == "chefe"
