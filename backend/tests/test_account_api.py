"""Minha conta: perfil, uso, acessos, senha, outras sessões, e-mail de verificação e notificações."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import LoginEvent
from audit.models import AuditLog
from datasets.models import Dashboard, Dataset, DatasetProfile
from tests.conftest import PASSWORD, ApiClient, code_of, logged_client, make_user

User = get_user_model()
pytestmark = pytest.mark.django_db

ROTAS = [
    ("get", "/me/profile"), ("put", "/me/profile"), ("get", "/me/logins"), ("post", "/me/sessions/revoke-others"),
    ("put", "/me/password"), ("post", "/me/email/request"), ("post", "/me/email/confirm"),
    ("get", "/me/notifications"), ("post", "/me/notifications/read"),
]


@pytest.mark.parametrize("metodo, caminho", ROTAS)
def test_todas_as_rotas_exigem_login(metodo, caminho):
    corpo = {"json": {}} if metodo in ("post", "put") else {}
    assert getattr(ApiClient(), metodo)(caminho, **corpo).status_code == 401


# ---------- perfil ----------


def test_perfil_traz_dados_e_uso_com_numeros_exatos(common, common_client):
    d1 = Dataset.objects.create(owner=common, original_name="a.csv", object_key="k1", format=".csv", size_bytes=100)
    Dataset.objects.create(owner=common, original_name="b.csv", object_key="k2", format=".csv", size_bytes=250)
    DatasetProfile.objects.create(dataset=d1, row_count=1, duplicate_row_count=0)
    Dashboard.objects.create(dataset=d1, owner=common, spec={})
    outro = make_user("outro")
    Dataset.objects.create(owner=outro, original_name="c.csv", object_key="k3", format=".csv", size_bytes=999)  # não conta

    corpo = common_client.get("/me/profile").json()
    assert corpo["username"] == "comum" and corpo["is_admin"] is False and corpo["email_masked"] is None
    assert corpo["usage"] == {"datasets": 2, "storage_bytes": 350, "profiled": 1, "dashboards": 1}
    assert corpo["member_since"]


def test_perfil_de_quem_nao_tem_nada_tem_uso_zerado(common_client):
    assert common_client.get("/me/profile").json()["usage"] == {"datasets": 0, "storage_bytes": 0, "profiled": 0, "dashboards": 0}


def test_salvar_perfil_substitui_nome_e_cor_e_vazio_limpa(common_client):
    salvo = common_client.put("/me/profile", json={"display_name": "  Maria Souza  ", "avatar_color": "violet"})
    assert salvo.status_code == 200 and salvo.json()["display_name"] == "Maria Souza" and salvo.json()["avatar_color"] == "violet"
    assert common_client.get("/me").json()["display_name"] == "Maria Souza"

    limpo = common_client.put("/me/profile", json={"display_name": "   ", "avatar_color": None})
    assert limpo.json()["display_name"] is None and limpo.json()["avatar_color"] is None


@pytest.mark.parametrize(
    "corpo",
    [
        {"display_name": "x" * 61},
        {"display_name": "nome\x00com controle"},
        {"avatar_color": "magenta"},
        {"avatar_color": "<script>"},
        {"is_admin": True},  # chave desconhecida: ninguém se promove por aqui
        {"display_name": "ok", "email": "x@y.com"},
    ],
)
def test_perfil_rejeita_entradas_invalidas(common_client, common, corpo):
    assert common_client.put("/me/profile", json=corpo).status_code == 422
    assert not User.objects.get(pk=common.pk).is_admin


def test_nome_malicioso_e_guardado_como_texto(common_client):
    nome = "<img src=x onerror=alert(1)>"
    common_client.put("/me/profile", json={"display_name": nome})
    assert common_client.get("/me").json()["display_name"] == nome  # a interface escapa na hora de exibir


# ---------- acessos ----------


def test_acessos_recentes_do_proprio_usuario_sem_ip(common, common_client):
    LoginEvent.objects.create(user=common, success=True, browser="Chrome · Windows")
    LoginEvent.objects.create(user=common, success=False, browser="Firefox · Linux")
    LoginEvent.objects.create(user=make_user("outro"), success=True, browser="Safari · macOS")
    lista = common_client.get("/me/logins").json()
    assert [(e["success"], e["browser"]) for e in lista] == [(False, "Firefox · Linux"), (True, "Chrome · Windows")]  # mais novo primeiro
    assert set(lista[0]) == {"success", "browser", "created_at"}


# ---------- senha e outras sessões ----------


def entrar(username="comum", senha=PASSWORD):
    cliente = ApiClient()
    assert cliente.post("/login", json={"username": username, "password": senha}).status_code == 200
    return cliente


def test_trocar_a_senha_mantem_esta_sessao_e_derruba_as_outras(common):
    esta, outra = entrar(), entrar()
    resposta = esta.put("/me/password", json={"current_password": PASSWORD, "new_password": "senha-nova-9"})
    assert resposta.status_code == 204
    assert esta.get("/me").status_code == 200  # a sessão que trocou a senha continua
    assert outra.get("/me").status_code == 401  # as outras caíram
    assert ApiClient().post("/login", json={"username": "comum", "password": "senha-nova-9"}).status_code == 200
    assert ApiClient().post("/login", json={"username": "comum", "password": PASSWORD}).status_code == 401
    assert AuditLog.objects.filter(action="change_own_password", actor=common).count() == 1


@pytest.mark.parametrize(
    "atual, nova, trecho",
    [("errada-123", "senha-nova-9", "Senha atual incorreta"), (PASSWORD, PASSWORD, "diferente da atual"), (PASSWORD, "curta", "pelo menos 8")],
)
def test_trocar_a_senha_valida_tudo(common_client, common, atual, nova, trecho):
    resposta = common_client.put("/me/password", json={"current_password": atual, "new_password": nova})
    assert resposta.status_code == 400 and trecho in resposta.json()["detail"]
    assert User.objects.get(pk=common.pk).check_password(PASSWORD)  # nada mudou


def test_encerrar_outras_sessoes_mantem_so_esta(common):
    esta, outra = entrar(), entrar()
    assert esta.post("/me/sessions/revoke-others").status_code == 204
    assert esta.get("/me").status_code == 200 and outra.get("/me").status_code == 401
    assert AuditLog.objects.filter(action="revoke_other_sessions", actor=common).count() == 1
    assert entrar().get("/me").status_code == 200  # dá para entrar de novo normalmente


# ---------- e-mail de verificação (a própria pessoa) ----------


def test_troca_do_proprio_email_pede_senha_e_confirma_no_endereco_novo(outbox):
    pessoa = make_user("p", email="antigo@exemplo.com")
    cliente = logged_client(pessoa)

    resposta = cliente.post("/me/email/request", json={"email": "Novo@Exemplo.com", "current_password": PASSWORD})
    assert resposta.status_code == 200 and resposta.json() == {"email_hint": "n***@exemplo.com", "resend_in": 30}
    assert len(outbox) == 1 and outbox[0][0] == "novo@exemplo.com"  # o código vai para o endereço NOVO
    assert cliente.get("/me").json()["email_masked"] == "a***@exemplo.com"  # ainda não mudou

    confirmado = cliente.post("/me/email/confirm", json={"code": code_of(outbox[0])})
    assert confirmado.status_code == 200 and confirmado.json() == {"email_masked": "n***@exemplo.com"}
    assert cliente.get("/me").json()["email_masked"] == "n***@exemplo.com" and cliente.get("/me/profile").json()["email_masked"] == "n***@exemplo.com"
    registro = AuditLog.objects.get(action="change_own_email")
    assert registro.actor == pessoa and registro.details == "a***@exemplo.com → n***@exemplo.com" and "novo@" not in registro.details

    ApiClient().post("/login", json={"username": "p", "password": PASSWORD})  # o próximo código de login vai ao endereço novo
    assert outbox[-1][0] == "novo@exemplo.com"


def test_troca_com_senha_errada_nao_envia_nada_e_repetir_bloqueia(common_client, outbox):
    for _ in range(5):
        assert common_client.post("/me/email/request", json={"email": "x@exemplo.com", "current_password": "errada-123"}).status_code == 400
    assert common_client.post("/me/email/request", json={"email": "x@exemplo.com", "current_password": PASSWORD}).status_code == 429
    assert outbox == []


def test_troca_recusa_email_igual_invalido_ou_de_outra_conta(outbox):
    pessoa = make_user("p", email="atual@exemplo.com")
    make_user("q", email="outro@exemplo.com")
    cliente = logged_client(pessoa)

    def pedir(email):
        return cliente.post("/me/email/request", json={"email": email, "current_password": PASSWORD})

    assert pedir("ATUAL@exemplo.com").status_code == 400 and pedir("lixo").status_code == 400
    assert pedir("outro@exemplo.com").status_code == 409
    assert outbox == []


def test_confirmacao_com_codigo_errado_esgota_e_sem_pedido_nao_ha_o_que_confirmar(outbox):
    pessoa = make_user("p")
    cliente = logged_client(pessoa)
    assert cliente.post("/me/email/confirm", json={"code": "123456"}).status_code == 400  # nada pendente

    cliente.post("/me/email/request", json={"email": "novo@exemplo.com", "current_password": PASSWORD})
    real = code_of(outbox[0])
    errado = "000000" if real != "000000" else "111111"
    for _ in range(4):
        assert cliente.post("/me/email/confirm", json={"code": errado}).status_code == 400
    ultima = cliente.post("/me/email/confirm", json={"code": errado})
    assert ultima.status_code == 400 and "Muitas tentativas" in ultima.json()["detail"]
    assert cliente.post("/me/email/confirm", json={"code": real}).status_code == 400  # esgotado
    assert User.objects.get(pk=pessoa.pk).email is None


def test_falha_no_envio_da_troca_descarta_o_codigo(monkeypatch):
    from accounts import account
    from core.mailer import MailSendError

    def quebra(*args):
        raise MailSendError

    monkeypatch.setattr(account, "send_email", quebra)
    pessoa = make_user("p")
    resposta = logged_client(pessoa).post("/me/email/request", json={"email": "novo@exemplo.com", "current_password": PASSWORD})
    assert resposta.status_code == 503 and not pessoa.email_codes.exists()


def test_rotas_de_email_rejeitam_chaves_desconhecidas(common_client):
    resposta = common_client.post("/me/email/request", json={"email": "a@exemplo.com", "current_password": PASSWORD, "is_admin": True})
    assert resposta.status_code == 422


def test_trocas_de_senha_e_email_exigem_csrf(common):
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.force_login(common)
    assert cliente.put("/me/password", json={"current_password": PASSWORD, "new_password": "senha-nova-9"}).status_code == 403
    assert cliente.post("/me/email/request", json={"email": "a@exemplo.com", "current_password": PASSWORD}).status_code == 403
    assert User.objects.get(pk=common.pk).check_password(PASSWORD)


# ---------- notificações ----------


def test_notificacoes_sao_so_do_dono_e_marcar_como_lidas_zera_o_contador(admin_client, common, common_client):
    alvo = make_user("alvo")
    admin_client.patch(f"/users/{alvo.pk}/email", json={"email": "alvo@exemplo.com"})
    dono = logged_client(alvo)
    antes = dono.get("/me/notifications").json()
    assert antes["unread"] == 1 and antes["items"][0]["read"] is False and antes["items"][0]["kind"] == "email_changed_by_admin"

    assert common_client.get("/me/notifications").json() == {"items": [], "unread": 0}  # outro usuário não vê
    assert dono.post("/me/notifications/read").status_code == 204
    depois = dono.get("/me/notifications").json()
    assert depois["unread"] == 0 and depois["items"][0]["read"] is True


def test_notificacoes_guardam_no_maximo_100_e_listam_20(common, common_client):
    from accounts.notifications import create_notification

    for i in range(105):
        create_notification(common, "k", f"aviso {i}")
    corpo = common_client.get("/me/notifications").json()
    assert corpo["unread"] == 100 and len(corpo["items"]) == 20 and corpo["items"][0]["message"] == "aviso 104"
