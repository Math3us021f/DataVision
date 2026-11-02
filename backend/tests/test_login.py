"""Login com senha, logout, /me, limite de tentativas, acessos registrados e CSRF."""

import pytest
from django.contrib.auth import get_user_model

from accounts import api as accounts_api
from accounts.models import LoginEvent
from tests.conftest import PASSWORD, ApiClient

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user("maria", PASSWORD)


def login(client, username="maria", password=PASSWORD, **extra):
    return client.post("/login", json={"username": username, "password": password}, **extra)


# ---------- login ----------


def test_login_correto_entrega_a_sessao(client, user):
    resposta = login(client)
    assert resposta.status_code == 200 and resposta.json() == {"status": "ok"}
    cookie = resposta.cookies["session"]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    assert client.get("/me").status_code == 200


def test_senha_errada_e_usuario_inexistente_recebem_a_mesma_resposta(client, user):
    errada = login(client, password="outra-senha-1")
    inexistente = login(client, username="ninguem")
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json() == {"detail": "Usuário ou senha inválidos"}  # não revela se a conta existe
    assert client.get("/me").status_code == 401


def test_conta_desativada_recebe_a_mesma_mensagem_generica(client, user):
    user.is_active = False
    user.save()
    resposta = login(client)
    assert resposta.status_code == 401 and resposta.json()["detail"] == "Usuário ou senha inválidos"
    assert client.get("/me").status_code == 401


def test_cookie_ganha_secure_quando_ligado(client, user, settings):
    assert "secure" not in login(client).cookies["session"].output().lower().replace("samesite", "")
    settings.SESSION_COOKIE_SECURE = True
    assert login(ApiClient()).cookies["session"]["secure"]


def test_senha_gigante_e_401_e_nao_erro(client, user):
    for nome in ("maria", "ninguem"):
        assert login(client, username=nome, password="x" * 5000).status_code == 401


def test_usuario_inexistente_gasta_a_mesma_verificacao_de_senha(client, user, monkeypatch):
    chamadas = []
    original = accounts_api.check_password
    monkeypatch.setattr(accounts_api, "check_password", lambda *a: (chamadas.append(a), original(*a))[1])
    login(client, username="ninguem")
    login(client, password="errada-1234")
    assert len(chamadas) == 2  # uma verificação em cada caso: o tempo de resposta não revela quais contas existem


def test_senhas_sao_guardadas_com_hash_pbkdf2(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]  # o de verdade, não o rápido dos testes
    user = User.objects.create_user("hash", PASSWORD)
    assert user.password.startswith("pbkdf2_sha256$") and PASSWORD not in user.password


# ---------- limite de tentativas ----------


def test_cinco_tentativas_erradas_bloqueiam_mesmo_com_a_senha_certa(client, user):
    for _ in range(5):
        assert login(client, password="errada-1234").status_code == 401
    bloqueado = login(client)  # a senha agora está certa, mas o bloqueio vale
    assert bloqueado.status_code == 429 and "Muitas tentativas" in bloqueado.json()["detail"]
    assert client.get("/me").status_code == 401


def test_bloqueio_e_por_usuario_e_um_acerto_zera_a_contagem(client, user):
    User.objects.create_user("outra", PASSWORD)
    for _ in range(5):
        login(client, password="errada-1234")
    assert login(client, username="outra").status_code == 200  # outro usuário não é afetado

    zerar = ApiClient()
    for _ in range(4):
        login(zerar, username="outra", password="errada-1234")
    assert login(zerar, username="outra").status_code == 200  # acertou antes do limite
    for _ in range(4):
        login(zerar, username="outra", password="errada-1234")
    assert login(zerar, username="outra").status_code == 200  # a contagem tinha zerado


# ---------- /me e logout ----------


def test_me_devolve_so_o_necessario(client, user):
    login(client)
    corpo = client.get("/me").json()
    assert corpo == {
        "username": "maria", "is_admin": False, "display_name": None, "avatar_color": None,
        "email_masked": None, "idle_timeout_seconds": 900,
    }  # sem hash de senha, sem chave de sessão


def test_me_mostra_nome_cor_e_email_mascarado(client):
    User.objects.create_user("ana", PASSWORD, email="ana.souza@exemplo.com", display_name="Ana Souza", preferences={"avatar_color": "violet"})
    client.force_login(User.objects.get(username="ana"))
    corpo = client.get("/me").json()
    assert corpo["display_name"] == "Ana Souza" and corpo["avatar_color"] == "violet"
    assert corpo["email_masked"] == "a***@exemplo.com" and "ana.souza" not in str(corpo)


def test_cor_de_avatar_fora_da_lista_e_ignorada(client):
    client.force_login(User.objects.create_user("c", PASSWORD, preferences={"avatar_color": "<script>"}))
    assert client.get("/me").json()["avatar_color"] is None


def test_me_sem_sessao_e_401_com_mensagem(client):
    resposta = client.get("/me")
    assert resposta.status_code == 401 and resposta.json() == {"detail": "Não autenticado"}


def test_logout_encerra_a_sessao_e_funciona_sem_sessao(client, user):
    login(client)
    assert client.post("/logout").json() == {"status": "ok"}
    assert client.get("/me").status_code == 401
    assert ApiClient().post("/logout").status_code == 200


def test_cookie_antigo_de_sessao_apagada_nao_vale(client, user):
    login(client)
    cookie = client.cookies["session"].value
    client.post("/logout")
    outro = ApiClient()
    outro.cookies["session"] = cookie  # quem copiou o cookie antes do logout não consegue reutilizá-lo
    assert outro.get("/me").status_code == 401


# ---------- acessos registrados ----------


def test_acessos_guardam_resultado_e_resumo_do_navegador_sem_ip(client, user):
    agente = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    login(client, password="errada-1234", HTTP_USER_AGENT=agente)
    login(client, HTTP_USER_AGENT=agente)
    eventos = list(LoginEvent.objects.filter(user=user).order_by("id"))
    assert [e.success for e in eventos] == [False, True]
    assert {e.browser for e in eventos} == {"Chrome · Windows"}
    assert {f.name for f in LoginEvent._meta.get_fields()} == {"id", "user", "success", "browser", "created_at"}  # nada de IP


def test_so_os_50_acessos_mais_recentes_ficam(client, user):
    for _ in range(55):
        login(client, password="errada-1234")
        from core import rate_limit

        rate_limit._failed_attempts.clear()  # não deixa o bloqueio atrapalhar este teste
    assert LoginEvent.objects.filter(user=user).count() == 50


# ---------- CSRF ----------


def test_login_exige_o_token_csrf_e_a_tela_de_login_entrega_o_cookie(user):
    cliente = ApiClient(enforce_csrf_checks=True)
    sem_token = cliente.post("/login", json={"username": "maria", "password": PASSWORD})
    assert sem_token.status_code == 403 and "CSRF" in sem_token.json()["detail"]

    cliente.get("/login")  # a tela de entrada define o cookie csrftoken
    token = cliente.cookies["csrftoken"].value
    com_token = cliente.post("/login", json={"username": "maria", "password": PASSWORD}, HTTP_X_CSRFTOKEN=token)
    assert com_token.status_code == 200


def test_token_csrf_errado_e_recusado(user):
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.get("/login")
    resposta = cliente.post("/login", json={"username": "maria", "password": PASSWORD}, HTTP_X_CSRFTOKEN="token-falso")
    assert resposta.status_code == 403


def test_logout_exige_csrf_mas_leituras_nao(user):
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.get("/login")
    token = cliente.cookies["csrftoken"].value
    cliente.post("/login", json={"username": "maria", "password": PASSWORD}, HTTP_X_CSRFTOKEN=token)
    assert cliente.get("/me").status_code == 200  # GET não precisa de token
    assert cliente.post("/logout").status_code == 403  # alterar estado precisa
    assert cliente.post("/logout", HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value).status_code == 200


def test_o_token_csrf_muda_ao_entrar(user):
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.get("/login")
    antes = cliente.cookies["csrftoken"].value
    cliente.post("/login", json={"username": "maria", "password": PASSWORD}, HTTP_X_CSRFTOKEN=antes)
    assert cliente.cookies["csrftoken"].value != antes  # o Django troca o token no login (protege contra fixação)


def test_respostas_usam_utf8_puro_como_o_fastapi(client):
    corpo = client.get("/me").content.decode("utf-8")
    assert "Não autenticado" in corpo
    escapado = chr(92) + "u00e3"  # a forma escapada do "ã" (barra invertida + u00e3), que não pode aparecer
    assert escapado not in corpo
