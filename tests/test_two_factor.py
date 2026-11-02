"""Verificação em dois passos por e-mail, cadastro do e-mail (admin e próprio usuário) e notificações."""

import os
import re
import smtplib
import uuid

import pytest
from fastapi.testclient import TestClient

import src.routers.api.account as account_router
import src.routers.api.login_2fa as login_router
from src.core import mailer
from src.core.db import get_connection
from src.core.logging_config import LOG_FILE_PATH, read_log_tail
from src.main import app
from src.services.verification import InvalidEmailError, mask_email, normalize_email

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
PASSWORD = "senha-123-x"


# ---------- apoio ----------


@pytest.fixture
def outbox(monkeypatch):
    """Captura os e-mails em vez de enviar: lista de (destinatário, assunto, corpo)."""
    sent = []

    def fake_send(to_address, subject, body):
        sent.append((to_address, subject, body))

    monkeypatch.setattr(login_router, "send_email", fake_send)
    monkeypatch.setattr(account_router, "send_email", fake_send)
    return sent


def code_of(message) -> str:
    return re.search(r"\b(\d{6})\b", message[2]).group(1)


@pytest.fixture
def admin():
    with TestClient(app) as c:
        assert c.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).json()["status"] == "ok"
        yield c


def make_user(admin, email=None, password=PASSWORD) -> tuple[str, int]:
    username = f"tf_{uuid.uuid4().hex[:8]}"
    body = {"username": username, "password": password}
    if email:
        body["email"] = email
    response = admin.post("/users", json=body)
    assert response.status_code == 201, response.text
    return username, response.json()["id"]


def unique_email(prefix="pessoa") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@exemplo.com"


def first_step(username, password=PASSWORD):
    client = TestClient(app)
    return client, client.post("/login", json={"username": username, "password": password})


def logged_in(username, outbox, password=PASSWORD) -> TestClient:
    client, response = first_step(username, password)
    assert response.json()["status"] == "2fa_required"
    assert client.post("/login/verify", json={"code": code_of(outbox[-1])}).status_code == 200
    return client


def sql(query, params=()):
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall() if cursor.description else []  # UPDATE/DELETE não devolvem linhas
        conn.commit()
        return rows


def age_code(user_id, purpose="login", **fields):
    """Envelhece o código no banco (em vez de esperar de verdade)."""
    sets = ", ".join(f"{name} = {value}" for name, value in fields.items())
    sql(f"UPDATE email_codes SET {sets} WHERE user_id = %s AND purpose = %s", (user_id, purpose))


# ---------- funções puras ----------


def test_mascara_do_email():
    assert mask_email("maria@gmail.com") == "m***@gmail.com"
    assert mask_email("a@b.co") == "a***@b.co"
    assert mask_email(None) is None and mask_email("") is None


@pytest.mark.parametrize("ruim", ["", "   ", "sem-arroba", "a@b", "a b@c.com", "a@b c.com", "x" * 250 + "@a.com", "a@b.com\nBcc: alguem@x.com"])
def test_email_invalido_e_recusado(ruim):
    with pytest.raises(InvalidEmailError):
        normalize_email(ruim)


def test_email_e_normalizado_para_minusculas():
    assert normalize_email("  Maria.Souza@Gmail.COM ") == "maria.souza@gmail.com"


# ---------- login em dois passos ----------


def test_conta_sem_email_continua_entrando_so_com_a_senha(admin, outbox):
    username, _ = make_user(admin)
    client, response = first_step(username)
    assert response.json() == {"status": "ok"}
    assert client.get("/me").status_code == 200
    assert outbox == []


def test_com_email_a_senha_certa_nao_da_sessao_e_envia_o_codigo(admin, outbox):
    email = unique_email()
    username, _ = make_user(admin, email)
    client, response = first_step(username)

    body = response.json()
    assert body["status"] == "2fa_required"
    assert body["email_hint"] == mask_email(email)
    assert body["resend_in"] == 30
    assert client.get("/me").status_code == 401  # ainda não há sessão
    assert "session" not in client.cookies
    assert len(outbox) == 1 and outbox[0][0] == email
    assert re.fullmatch(r"\d{6}", code_of(outbox[0]))
    assert code_of(outbox[0]) not in response.text  # o código só viaja por e-mail


def test_codigo_certo_conclui_o_login_e_so_vale_uma_vez(admin, outbox):
    username, _ = make_user(admin, unique_email())
    client, _ = first_step(username)
    code = code_of(outbox[0])

    done = client.post("/login/verify", json={"code": code})
    assert done.status_code == 200 and done.json() == {"status": "ok"}
    me = client.get("/me").json()
    assert me["username"] == username and me["email_masked"].endswith("@exemplo.com")

    outro = TestClient(app)
    assert outro.post("/login", json={"username": username, "password": PASSWORD}).json()["status"] == "2fa_required"
    # o código antigo já foi consumido (e o novo login pediu outro): reutilizar não funciona
    assert outro.post("/login/verify", json={"code": code}).status_code == 401


def test_codigo_aceita_espacos_ao_redor(admin, outbox):
    username, _ = make_user(admin, unique_email())
    client, _ = first_step(username)
    code = code_of(outbox[0])
    assert client.post("/login/verify", json={"code": f" {code[:3]} {code[3:]} "}).status_code == 200


def test_codigo_errado_conta_tentativas_e_esgota_na_quinta(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    client, _ = first_step(username)
    real = code_of(outbox[0])
    errado = "000000" if real != "000000" else "111111"

    esperado = ["4 tentativas", "3 tentativas", "2 tentativas", "1 tentativa"]
    for restante in esperado:
        resposta = client.post("/login/verify", json={"code": errado})
        assert resposta.status_code == 401 and restante in resposta.json()["detail"]
    ultima = client.post("/login/verify", json={"code": errado})
    assert ultima.status_code == 401 and "Muitas tentativas" in ultima.json()["detail"]

    # esgotado: nem o código certo vale mais; é preciso recomeçar pela senha
    assert client.post("/login/verify", json={"code": real}).status_code == 401
    assert client.get("/me").status_code == 401
    assert sql("SELECT 1 FROM email_codes WHERE user_id = %s AND purpose = 'login'", (user_id,)) == []


def test_formato_invalido_de_codigo_conta_como_tentativa_errada(admin, outbox):
    username, _ = make_user(admin, unique_email())
    client, _ = first_step(username)
    for lixo in ("abc", "12345", "1234567", "' OR 1=1 --", ""):
        assert client.post("/login/verify", json={"code": lixo}).status_code == 401
    assert client.get("/me").status_code == 401


def test_codigo_vencido_e_recusado(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    client, _ = first_step(username)
    age_code(user_id, expires_at="now() - interval '1 minute'")
    resposta = client.post("/login/verify", json={"code": code_of(outbox[0])})
    assert resposta.status_code == 401 and "expirou" in resposta.json()["detail"]


def test_verificar_sem_ter_passado_pela_senha_nao_funciona(admin, outbox):
    username, _ = make_user(admin, unique_email())
    first_step(username)  # gera um código válido, mas este cliente não tem o cookie da etapa
    sem_cookie = TestClient(app)
    assert sem_cookie.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 401

    adulterado = TestClient(app)
    adulterado.cookies.set("pending_login", "valor.adulterado.qualquer")
    assert adulterado.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 401


def test_cookie_da_etapa_nao_serve_como_sessao(admin, outbox):
    username, _ = make_user(admin, unique_email())
    client, _ = first_step(username)
    assert "pending_login" in client.cookies
    for caminho in ("/me", "/datasets", "/dashboard/summary", "/me/notifications"):
        assert client.get(caminho).status_code == 401, caminho
    # já o endpoint da etapa aceita o cookie dela (429 = reconheceu a pessoa, só pede para esperar a pausa do reenvio)
    assert client.post("/login/resend").status_code == 429


def test_codigo_de_um_usuario_nao_serve_para_outro(admin, outbox):
    a, _ = make_user(admin, unique_email())
    b, _ = make_user(admin, unique_email())
    client_a, _ = first_step(a)
    client_b, _ = first_step(b)
    codigo_a, codigo_b = code_of(outbox[0]), code_of(outbox[1])
    if codigo_a != codigo_b:  # (6 dígitos: coincidir é raro, e nesse caso o teste não prova nada)
        assert client_b.post("/login/verify", json={"code": codigo_a}).status_code == 401
    assert client_a.post("/login/verify", json={"code": codigo_a}).status_code == 200


def test_reenvio_so_depois_da_pausa_e_invalida_o_codigo_anterior(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    client, _ = first_step(username)
    antigo = code_of(outbox[0])

    cedo = client.post("/login/resend")
    assert cedo.status_code == 429 and len(outbox) == 1

    age_code(user_id, last_sent_at="now() - interval '31 seconds'")
    ok = client.post("/login/resend")
    assert ok.status_code == 200 and ok.json()["resend_in"] == 30 and len(outbox) == 2
    novo = code_of(outbox[1])
    if novo != antigo:
        assert client.post("/login/verify", json={"code": antigo}).status_code == 401
    assert client.post("/login/verify", json={"code": novo}).status_code == 200


def test_entrar_de_novo_logo_em_seguida_nao_manda_outro_email(admin, outbox):
    username, _ = make_user(admin, unique_email())
    first_step(username)
    client, segunda = first_step(username)
    assert segunda.json()["status"] == "2fa_required" and segunda.json()["resend_in"] == 0
    assert len(outbox) == 1  # o primeiro código continua valendo
    assert client.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 200


def test_limite_de_codigos_por_hora(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    first_step(username)
    age_code(user_id, last_sent_at="now() - interval '1 minute'", sends_in_window="10")
    _, resposta = first_step(username)
    assert resposta.status_code == 429 and len(outbox) == 1


def test_falha_no_envio_bloqueia_o_login_sem_vazar_sessao_nem_deixar_codigo(admin, monkeypatch):
    username, user_id = make_user(admin, unique_email())

    def quebra(*args):
        raise mailer.MailSendError

    monkeypatch.setattr(login_router, "send_email", quebra)
    client, resposta = first_step(username)
    assert resposta.status_code == 503
    assert "session" not in client.cookies and "pending_login" not in client.cookies
    assert client.get("/me").status_code == 401
    assert sql("SELECT 1 FROM email_codes WHERE user_id = %s", (user_id,)) == []


def test_sem_smtp_configurado_o_login_com_email_tambem_e_bloqueado(admin, monkeypatch):
    username, _ = make_user(admin, unique_email())
    for nome in ("SMTP_HOST", "SMTP_FROM"):
        monkeypatch.delenv(nome, raising=False)
    _, resposta = first_step(username)
    assert resposta.status_code == 503


def test_codigo_e_guardado_so_como_hash_e_nao_vai_para_o_log(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    first_step(username)
    code = code_of(outbox[0])

    guardado = sql("SELECT code_hash FROM email_codes WHERE user_id = %s AND purpose = 'login'", (user_id,))[0]["code_hash"]
    assert guardado != code and len(guardado) == 64 and code not in guardado
    assert not any(f" {code}" in linha or f"={code}" in linha for linha in read_log_tail(LOG_FILE_PATH, 300))


def test_conta_desativada_ou_senha_trocada_no_meio_derruba_a_verificacao(admin, outbox):
    a, id_a = make_user(admin, unique_email())
    client_a, _ = first_step(a)
    admin.patch(f"/users/{id_a}", json={"is_active": False})
    assert client_a.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 401

    b, id_b = make_user(admin, unique_email())
    client_b, _ = first_step(b)
    admin.put(f"/users/{id_b}/password", json={"new_password": "outra-senha-9"})
    assert client_b.post("/login/verify", json={"code": code_of(outbox[1])}).status_code == 401


def test_email_com_maiusculas_recebe_o_codigo_no_endereco_normalizado(admin, outbox):
    sufixo = uuid.uuid4().hex[:8]
    username, _ = make_user(admin, f"Pessoa.Maiuscula{sufixo}@Exemplo.COM")
    first_step(username)
    assert outbox[0][0] == f"pessoa.maiuscula{sufixo}@exemplo.com"


def test_senha_errada_com_email_nao_envia_nada(admin, outbox):
    username, _ = make_user(admin, unique_email())
    _, resposta = first_step(username, "senha-errada-1")
    assert resposta.status_code == 401 and outbox == []


# ---------- admin cadastra e altera o e-mail ----------


def test_criar_usuario_com_email_mostra_so_a_versao_mascarada(admin):
    email = unique_email("Maria")
    response = admin.post("/users", json={"username": f"tf_{uuid.uuid4().hex[:8]}", "password": PASSWORD, "email": email})
    assert response.status_code == 201
    assert response.json()["email_masked"] == mask_email(email.lower())
    assert email.lower() not in response.text  # o e-mail inteiro nunca volta pela API


def test_lista_de_usuarios_mascara_o_email(admin):
    email = unique_email("zelia")
    username, _ = make_user(admin, email)
    lista = admin.get("/users", params={"search": username})
    assert lista.json()["items"][0]["email_masked"] == mask_email(email)
    assert email not in lista.text


def test_email_invalido_ou_repetido_na_criacao(admin):
    ruim = admin.post("/users", json={"username": f"tf_{uuid.uuid4().hex[:8]}", "password": PASSWORD, "email": "isso-nao-e-email"})
    assert ruim.status_code == 400

    email = unique_email()
    make_user(admin, email)
    repetido = admin.post("/users", json={"username": f"tf_{uuid.uuid4().hex[:8]}", "password": PASSWORD, "email": email.upper()})
    assert repetido.status_code == 409  # sem diferenciar maiúsculas


def test_admin_define_email_pessoa_e_avisada_no_sistema_e_a_auditoria_registra(admin, outbox):
    username, user_id = make_user(admin)
    email = unique_email("nova")

    resposta = admin.patch(f"/users/{user_id}/email", json={"email": email})
    assert resposta.status_code == 200 and resposta.json()["email_masked"] == mask_email(email)
    assert outbox == []  # sem confirmação por e-mail quando é o admin

    cliente, login = first_step(username)  # a partir de agora o login pede o código
    assert login.json()["status"] == "2fa_required"
    pessoa = logged_in(username, outbox)
    avisos = pessoa.get("/me/notifications").json()
    assert avisos["unread"] == 1
    assert mask_email(email) in avisos["items"][0]["message"] and email not in avisos["items"][0]["message"]

    auditoria = admin.get("/audit-logs", params={"search": username, "action": "admin_change_email"}).json()["items"][0]
    assert auditoria["actor_username"] == ADMIN_USERNAME and "sem e-mail" in auditoria["details"]
    assert email not in str(auditoria)  # só a versão mascarada vai para a auditoria

    pessoa.post("/me/notifications/read")
    assert pessoa.get("/me/notifications").json()["unread"] == 0


def test_admin_remove_o_email_e_o_login_volta_a_pedir_so_a_senha(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    resposta = admin.patch(f"/users/{user_id}/email", json={"email": None})
    assert resposta.status_code == 200 and resposta.json()["email_masked"] is None

    client, login = first_step(username)
    assert login.json() == {"status": "ok"}
    aviso = client.get("/me/notifications").json()["items"][0]["message"]
    assert "removeu" in aviso


def test_trocar_o_email_descarta_codigos_pendentes_do_antigo(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    client, _ = first_step(username)
    antigo = code_of(outbox[0])
    admin.patch(f"/users/{user_id}/email", json={"email": unique_email()})
    assert client.post("/login/verify", json={"code": antigo}).status_code == 401


def test_admin_nao_altera_o_proprio_email_por_aqui(admin):
    meu_id = admin.get("/users", params={"search": ADMIN_USERNAME}).json()["items"][0]["id"]
    resposta = admin.patch(f"/users/{meu_id}/email", json={"email": unique_email()})
    assert resposta.status_code == 400 and "Minha conta" in resposta.json()["detail"]


def test_alterar_email_de_outro_valida_permissao_usuario_existencia_e_formato(admin):
    username, user_id = make_user(admin)
    comum = TestClient(app)
    comum.post("/login", json={"username": username, "password": PASSWORD})
    assert comum.patch(f"/users/{user_id}/email", json={"email": unique_email()}).status_code == 403
    assert TestClient(app).patch(f"/users/{user_id}/email", json={"email": unique_email()}).status_code == 401
    assert admin.patch("/users/99999999/email", json={"email": unique_email()}).status_code == 404
    assert admin.patch(f"/users/{user_id}/email", json={"email": "invalido"}).status_code == 400
    outro_email = unique_email()
    make_user(admin, outro_email)
    assert admin.patch(f"/users/{user_id}/email", json={"email": outro_email}).status_code == 409


def test_notificacoes_sao_so_do_dono(admin):
    a, id_a = make_user(admin)
    b, _ = make_user(admin)
    admin.patch(f"/users/{id_a}/email", json={"email": unique_email()})
    cliente_b = TestClient(app)
    cliente_b.post("/login", json={"username": b, "password": PASSWORD})
    assert cliente_b.get("/me/notifications").json() == {"items": [], "unread": 0}
    assert TestClient(app).get("/me/notifications").status_code == 401


# ---------- a própria pessoa troca o e-mail ----------


def test_troca_do_proprio_email_pede_senha_e_confirma_no_endereco_novo(admin, outbox):
    antigo, novo = unique_email("antigo"), unique_email("novo")
    username, user_id = make_user(admin, antigo)
    pessoa = logged_in(username, outbox)
    outbox.clear()

    resposta = pessoa.post("/me/email/request", json={"email": novo, "current_password": PASSWORD})
    assert resposta.status_code == 200 and resposta.json()["email_hint"] == mask_email(novo)
    assert len(outbox) == 1 and outbox[0][0] == novo  # o código vai para o endereço NOVO
    assert pessoa.get("/me").json()["email_masked"] == mask_email(antigo)  # ainda não mudou

    confirmado = pessoa.post("/me/email/confirm", json={"code": code_of(outbox[0])})
    assert confirmado.status_code == 200 and confirmado.json()["email_masked"] == mask_email(novo)
    assert pessoa.get("/me").json()["email_masked"] == mask_email(novo)
    assert pessoa.get("/me/profile").json()["email_masked"] == mask_email(novo)

    auditoria = admin.get("/audit-logs", params={"search": username, "action": "change_own_email"}).json()["items"][0]
    assert auditoria["actor_username"] == username and novo not in str(auditoria)

    first_step(username)  # o próximo código de login vai para o novo endereço
    assert outbox[-1][0] == novo


def test_troca_com_senha_errada_nao_envia_nada_e_repetir_bloqueia(admin, outbox):
    username, _ = make_user(admin, unique_email())
    pessoa = logged_in(username, outbox)
    outbox.clear()
    for _ in range(5):
        r = pessoa.post("/me/email/request", json={"email": unique_email(), "current_password": "errada-123"})
        assert r.status_code == 400
    assert pessoa.post("/me/email/request", json={"email": unique_email(), "current_password": PASSWORD}).status_code == 429
    assert outbox == []


def test_troca_recusa_email_igual_invalido_ou_de_outra_conta(admin, outbox):
    atual, outro = unique_email(), unique_email()
    username, _ = make_user(admin, atual)
    make_user(admin, outro)
    pessoa = logged_in(username, outbox)

    def pedir(email):
        return pessoa.post("/me/email/request", json={"email": email, "current_password": PASSWORD})

    assert pedir(atual.upper()).status_code == 400  # o mesmo, mesmo com maiúsculas
    assert pedir("lixo").status_code == 400
    assert pedir(outro).status_code == 409


def test_confirmacao_com_codigo_errado_esgota_e_sem_pedido_nao_ha_o_que_confirmar(admin, outbox):
    username, user_id = make_user(admin, unique_email())
    pessoa = logged_in(username, outbox)
    assert pessoa.post("/me/email/confirm", json={"code": "123456"}).status_code == 400  # nada pendente

    novo = unique_email()
    pessoa.post("/me/email/request", json={"email": novo, "current_password": PASSWORD})
    real = code_of(outbox[-1])
    errado = "000000" if real != "000000" else "111111"
    for _ in range(4):
        assert pessoa.post("/me/email/confirm", json={"code": errado}).status_code == 400
    ultima = pessoa.post("/me/email/confirm", json={"code": errado})
    assert ultima.status_code == 400 and "Muitas tentativas" in ultima.json()["detail"]
    assert pessoa.post("/me/email/confirm", json={"code": real}).status_code == 400  # esgotado
    assert sql("SELECT email FROM users WHERE id = %s", (user_id,))[0]["email"] != novo  # nada foi alterado


def test_quem_nao_tinha_email_cadastra_o_primeiro_e_passa_a_usar_o_segundo_passo(admin, outbox):
    username, _ = make_user(admin)
    client, login = first_step(username)
    assert login.json() == {"status": "ok"} and client.get("/me").json()["email_masked"] is None

    email = unique_email()
    client.post("/me/email/request", json={"email": email, "current_password": PASSWORD})
    assert client.post("/me/email/confirm", json={"code": code_of(outbox[-1])}).status_code == 200
    _, proximo = first_step(username)
    assert proximo.json()["status"] == "2fa_required"


def test_rotas_de_email_exigem_login_e_rejeitam_chaves_desconhecidas(admin, outbox):
    anonimo = TestClient(app)
    assert anonimo.post("/me/email/request", json={"email": "a@b.com", "current_password": "x"}).status_code == 401
    assert anonimo.post("/me/email/confirm", json={"code": "123456"}).status_code == 401

    username, _ = make_user(admin)
    pessoa, _ = first_step(username)
    extra = pessoa.post("/me/email/request", json={"email": unique_email(), "current_password": PASSWORD, "is_admin": True})
    assert extra.status_code == 422


# ---------- envio SMTP ----------


class FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls, self.message = host, port, [], None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, message):
        self.message = message
        self.calls.append("send")


@pytest.fixture
def smtp_env(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    for nome, valor in {"SMTP_HOST": "smtp.exemplo.com", "SMTP_PORT": "587", "SMTP_SECURITY": "starttls",
                        "SMTP_USER": "sistema@exemplo.com", "SMTP_PASSWORD": "segredo", "SMTP_FROM": "sistema@exemplo.com"}.items():
        monkeypatch.setenv(nome, valor)


def test_envio_starttls_com_login(smtp_env):
    mailer.send_email("alguem@exemplo.com", "Assunto", "Corpo 123456")
    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.exemplo.com", 587)
    assert smtp.calls == ["starttls", ("login", "sistema@exemplo.com"), "send"]
    assert smtp.message["To"] == "alguem@exemplo.com" and smtp.message["From"] == "sistema@exemplo.com"


def test_envio_sem_tls_nem_login_para_o_coletor_local(smtp_env, monkeypatch):
    monkeypatch.setenv("SMTP_SECURITY", "none")
    monkeypatch.setenv("SMTP_USER", "")
    mailer.send_email("alguem@exemplo.com", "A", "B")
    assert FakeSMTP.instances[0].calls == ["send"]


def test_sem_configuracao_e_erro_de_servidor_viram_erros_proprios(smtp_env, monkeypatch):
    class Quebrado(FakeSMTP):
        def send_message(self, message):
            raise smtplib.SMTPRecipientsRefused({})

    monkeypatch.setattr(mailer.smtplib, "SMTP", Quebrado)
    with pytest.raises(mailer.MailSendError):
        mailer.send_email("a@b.com", "A", "B")

    monkeypatch.delenv("SMTP_HOST")
    with pytest.raises(mailer.MailNotConfiguredError):
        mailer.send_email("a@b.com", "A", "B")


@pytest.mark.parametrize("porta, esperado", [("587", ["starttls", ("login", "u"), "send"]), ("465", [("login", "u"), "send"]), ("1025", [("login", "u"), "send"])])
def test_seguranca_do_envio_sem_smtp_security_vem_da_porta(smtp_env, monkeypatch, porta, esperado):
    monkeypatch.delenv("SMTP_SECURITY")
    monkeypatch.setenv("SMTP_PORT", porta)
    monkeypatch.setenv("SMTP_USER", "u")
    mailer.send_email("alguem@exemplo.com", "A", "B")
    assert FakeSMTP.instances[0].calls == esperado  # só a 587 faz STARTTLS (a 465 já nasce em SSL; a 1025 é o coletor local)
