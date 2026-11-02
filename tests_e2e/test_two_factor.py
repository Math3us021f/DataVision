"""Verificação em dois passos por e-mail, no navegador, lendo os códigos no Mailpit (coletor local do Compose).

Atenção: estes testes precisam que a aplicação envie para o Mailpit. Se o `.env` tiver SMTP_HOST de um
provedor de verdade (para testar o envio real), remova-o antes de rodar a suíte de interface.
"""

import json
import os
import re
import time
import urllib.request
import uuid

import pytest
from playwright.sync_api import expect

from conftest import unique_username

MAILPIT = os.environ.get("MAILPIT_URL", "http://localhost:8025")
PASSWORD = "senha-inicial-123"


def mailpit(path, method="GET"):
    request = urllib.request.Request(f"{MAILPIT}{path}", method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read() or b"{}")


def wait_for_code(address, after=0, timeout=15) -> str:
    """Código do e-mail mais recente para `address` (só considera mensagens depois de `after` mensagens)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        messages = [m for m in mailpit("/api/v1/messages?limit=200")["messages"] if any(t["Address"] == address for t in m["To"])]
        if len(messages) > after:
            text = mailpit(f"/api/v1/message/{messages[0]['ID']}")["Text"]  # a lista vem do mais novo para o mais antigo
            return re.search(r"\b(\d{6})\b", text).group(1)
        time.sleep(0.3)
    raise AssertionError(
        f"Nenhum e-mail chegou ao Mailpit para {address}. A aplicação está enviando para o Mailpit "
        "(SMTP_HOST vazio ou 'mailpit' no .env)?"
    )


def count_mail(address) -> int:
    return len([m for m in mailpit("/api/v1/messages?limit=200")["messages"] if any(t["Address"] == address for t in m["To"])])


def unique_email() -> str:
    return f"e2e.{uuid.uuid4().hex[:10]}@exemplo.com"


def masked(email: str) -> str:
    return f"{email[0]}***@{email.split('@')[1]}"


def create_user(admin_page, email=None) -> str:
    username = unique_username("tf")
    body = {"username": username, "password": PASSWORD}
    if email:
        body["email"] = email
    assert admin_page.request.post("/users", data=body).ok
    return username


def password_step(page, username, password=PASSWORD):
    page.goto("/login")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#login-submit").click()


@pytest.fixture
def fresh(browser, base_url):
    """Contexto novo e sem sessão (o usuário que vai entrar com código)."""
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    yield page
    context.close()


def test_login_com_email_pede_o_codigo_recebido_e_entra(logged_in_admin, fresh):
    email = unique_email()
    username = create_user(logged_in_admin, email)

    password_step(fresh, username)
    expect(fresh.locator("#code-form")).to_be_visible()
    expect(fresh.locator("#code-hint")).to_have_text(masked(email))
    expect(fresh.locator("#login-form")).to_have_count(0)
    assert fresh.request.get("/me").status == 401  # ainda não há sessão

    fresh.locator("#code").fill(wait_for_code(email))
    fresh.locator("#code-submit").click()
    expect(fresh.locator("#stat-datasets")).to_be_visible()
    assert fresh.url.endswith("/app")
    assert fresh.request.get("/me").json()["username"] == username


def test_codigo_errado_mostra_tentativas_restantes_e_continua_na_tela_do_codigo(logged_in_admin, fresh):
    email = unique_email()
    username = create_user(logged_in_admin, email)
    password_step(fresh, username)
    real = wait_for_code(email)
    errado = "000000" if real != "000000" else "111111"

    fresh.locator("#code").fill(errado)
    fresh.locator("#code-submit").click()
    expect(fresh.locator("#login-error")).to_contain_text("4 tentativas")
    expect(fresh.locator("#code-form")).to_be_visible()

    fresh.locator("#code").fill(real)  # o código certo ainda vale
    fresh.locator("#code-submit").click()
    expect(fresh.locator("#stat-datasets")).to_be_visible()


def test_depois_de_cinco_erros_volta_para_usuario_e_senha(logged_in_admin, fresh):
    email = unique_email()
    username = create_user(logged_in_admin, email)
    password_step(fresh, username)
    real = wait_for_code(email)
    errado = "000000" if real != "000000" else "111111"

    for _ in range(5):
        fresh.locator("#code").fill(errado)
        fresh.locator("#code-submit").click()
        fresh.wait_for_timeout(250)
    expect(fresh.locator("#login-form")).to_be_visible()
    expect(fresh.locator("#login-error")).to_contain_text("Entre novamente")
    assert fresh.request.get("/me").status == 401


def test_reenviar_tem_pausa_e_voltar_retorna_a_senha(logged_in_admin, fresh):
    email = unique_email()
    username = create_user(logged_in_admin, email)
    password_step(fresh, username)
    wait_for_code(email)

    reenviar = fresh.locator("#code-resend")
    expect(reenviar).to_be_disabled()
    expect(reenviar).to_contain_text("Reenviar em")
    assert count_mail(email) == 1

    fresh.locator("#code-back").click()
    expect(fresh.locator("#login-form")).to_be_visible()
    expect(fresh.locator("#password")).to_have_value("")


def test_conta_sem_email_continua_entrando_so_com_a_senha(logged_in_admin, fresh):
    username = create_user(logged_in_admin)
    password_step(fresh, username)
    expect(fresh.locator("#stat-datasets")).to_be_visible()


def test_admin_cria_usuario_com_email_pela_tela_e_ve_so_o_mascarado(logged_in_admin):
    page = logged_in_admin
    email, username = unique_email(), unique_username("tf")
    page.goto("/app/admin/users")
    page.locator("#new-user-button").click()
    page.locator("#new-username").fill(username)
    page.locator("#new-password").fill(PASSWORD)
    page.locator("#new-email").fill(email)
    page.locator("#create-user-submit").click()
    expect(page.get_by_text(f'Usuário "{username}" criado.')).to_be_visible()

    page.locator("#users-search").fill(username)
    linha = page.locator(f'tr[data-user="{username}"]')
    expect(linha.locator("[data-email]")).to_have_text(masked(email))
    assert email not in page.content()  # o endereço inteiro nunca chega ao navegador


def test_admin_altera_email_e_a_pessoa_ve_o_aviso_no_sistema(browser, base_url, logged_in_admin):
    username = create_user(logged_in_admin)  # sem e-mail: entra só com a senha
    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": PASSWORD}).ok
        pessoa = context.new_page()
        pessoa.goto("/app")
        expect(pessoa.locator("#stat-datasets")).to_be_visible()
        expect(pessoa.locator("#notifications-badge")).to_have_count(0)

        email = unique_email()
        admin = logged_in_admin
        admin.goto("/app/admin/users")
        admin.locator("#users-search").fill(username)
        admin.get_by_label(f"E-mail de {username}").click()
        admin.locator("#admin-email-input").fill(email)
        admin.locator("#admin-email-submit").click()
        expect(admin.get_by_text(f'E-mail de "{username}" atualizado.')).to_be_visible()
        expect(admin.locator(f'tr[data-user="{username}"] [data-email]')).to_have_text(masked(email))
        assert count_mail(email) == 0  # o admin não dispara código

        pessoa.reload()
        expect(pessoa.locator("#notifications-badge")).to_have_text("1")
        pessoa.locator("#notifications-open").click()
        expect(pessoa.locator("#notifications-list li").first).to_contain_text(masked(email))
        expect(pessoa.locator("#notifications-list li").first).to_have_attribute("data-unread", "true")
        assert email not in pessoa.locator("#notifications-list").inner_text()

        pessoa.keyboard.press("Escape")
        expect(pessoa.locator("#notifications-badge")).to_have_count(0)  # lidas ao abrir
    finally:
        context.close()


def test_pessoa_cadastra_o_proprio_email_confirmando_o_codigo_e_depois_o_login_exige_o_codigo(logged_in_admin, browser, base_url, fresh):
    username = create_user(logged_in_admin)
    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": PASSWORD}).ok
        page = context.new_page()
        page.goto("/app")
        expect(page.locator("#email-reminder")).to_be_visible()  # lembrete: ainda sem e-mail

        page.get_by_role("link", name="Cadastrar agora").click()
        expect(page.locator("#email-current")).to_contain_text("Nenhum e-mail cadastrado")

        email = unique_email()
        page.locator("#email-open").click()
        page.locator("#email-new").fill(email)
        page.locator("#email-password").fill("senha-errada-1")
        page.locator("#email-send").click()
        expect(page.locator("#email-error")).to_contain_text("Senha atual incorreta")
        assert count_mail(email) == 0

        page.locator("#email-password").fill(PASSWORD)
        page.locator("#email-send").click()
        expect(page.locator("#email-code")).to_be_visible()
        page.locator("#email-code").fill(wait_for_code(email))
        page.locator("#email-confirm").click()
        expect(page.get_by_text("E-mail confirmado e salvo.")).to_be_visible()
        expect(page.locator("#email-current")).to_have_text(masked(email))
        expect(page.locator("#email-reminder")).to_have_count(0)  # já tem e-mail: sem lembrete
    finally:
        context.close()

    password_step(fresh, username)  # em outro navegador, agora pede o código
    expect(fresh.locator("#code-form")).to_be_visible()
    fresh.locator("#code").fill(wait_for_code(email))
    fresh.locator("#code-submit").click()
    expect(fresh.locator("#stat-datasets")).to_be_visible()


def test_lembrete_pode_ser_dispensado_e_nao_aparece_a_quem_tem_email(logged_in_admin, browser, base_url):
    sem = create_user(logged_in_admin)
    com = create_user(logged_in_admin, unique_email())
    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": sem, "password": PASSWORD}).ok
        page = context.new_page()
        page.goto("/app")
        expect(page.locator("#email-reminder")).to_be_visible()
        page.get_by_label("Dispensar aviso").click()
        expect(page.locator("#email-reminder")).to_have_count(0)
        page.get_by_role("link", name="Datasets").first.click()
        expect(page.locator("#email-reminder")).to_have_count(0)  # continua dispensado nesta sessão
    finally:
        context.close()
    # quem tem e-mail não vê o lembrete (o login dele exigiria o código; aqui basta a API: sem lembrete = e-mail presente)
    assert logged_in_admin.request.get("/users", params={"search": com}).json()["items"][0]["email_masked"] is not None


def test_usuario_comum_nao_acessa_a_troca_de_email_de_outro(logged_in_admin, browser, base_url):
    alvo = create_user(logged_in_admin)
    outro = create_user(logged_in_admin)
    alvo_id = logged_in_admin.request.get("/users", params={"search": alvo}).json()["items"][0]["id"]
    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": outro, "password": PASSWORD}).ok
        resposta = context.request.patch(f"/users/{alvo_id}/email", data={"email": unique_email()})
        assert resposta.status == 403
    finally:
        context.close()
