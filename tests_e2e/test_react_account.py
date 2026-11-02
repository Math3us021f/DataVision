"""Nova interface (React) — Minha conta: perfil (nome e avatar de iniciais), segurança e atividade."""

import re

import pytest
from playwright.sync_api import expect

from conftest import unique_username

PASSWORD = "senha-inicial-123"
XSS = "<img src=x onerror=window.__xss=1>"


@pytest.fixture
def account(browser, base_url, logged_in_admin):
    """Usuário comum novo, com 1 dataset. Devolve (context, page em /app/account, username)."""
    username = unique_username("conta")
    assert logged_in_admin.request.post("/users", data={"username": username, "password": PASSWORD}).ok
    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": PASSWORD}).ok
        upload = context.request.post(
            "/datasets/upload", multipart={"file": {"name": "v.csv", "mimeType": "text/csv", "buffer": b"a,b\n1,2\n"}}
        )
        assert upload.ok
        page = context.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto("/app/account")
        expect(page.locator("#usage")).to_be_visible()
        yield context, page, username
    finally:
        context.close()


def test_anonimo_e_redirecionado_para_o_login(page):
    page.goto("/app/account")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_abas_trocam_pela_url_e_aba_invalida_cai_no_perfil(account):
    _, page, _ = account
    expect(page.get_by_role("tab", name="Perfil")).to_have_attribute("aria-selected", "true")

    page.get_by_role("tab", name="Segurança").click()
    expect(page).to_have_url(re.compile(r"\?aba=seguranca$"))
    expect(page.get_by_text("Trocar senha", exact=True)).to_be_visible()

    page.goto("/app/account?aba=atividade")
    expect(page.get_by_role("tab", name="Atividade")).to_have_attribute("aria-selected", "true")

    page.goto("/app/account?aba=qualquer-coisa")
    expect(page.get_by_role("tab", name="Perfil")).to_have_attribute("aria-selected", "true")


def test_perfil_mostra_conta_e_uso_com_numeros_exatos(account):
    _, page, username = account
    expect(page.get_by_text(f"@{username}")).to_be_visible()
    expect(page.get_by_text("Usuário", exact=True).first).to_be_visible()
    uso = page.locator("#usage")
    expect(uso).to_contain_text("Datasets")
    expect(uso.locator("div", has_text="Datasets").locator("dd").first).to_have_text("1")
    expect(uso.locator("div", has_text="Espaço usado").locator("dd").first).to_have_text("8 B")
    expect(uso.locator("div", has_text="Perfilados").locator("dd").first).to_have_text("0")


def test_salvar_nome_e_cor_atualiza_menu_cabecalho_e_saudacao_e_persiste(account):
    _, page, username = account
    salvar = page.get_by_role("button", name="Salvar alterações")
    expect(salvar).to_be_disabled()  # nada mudou ainda

    page.get_by_label("Nome de exibição").fill("Maria Souza")
    page.get_by_role("radio", name="Violeta").click()
    expect(page.locator("#profile-preview-name")).to_have_text("Maria Souza")  # prévia ao vivo
    expect(salvar).to_be_enabled()
    salvar.click()

    expect(page.get_by_text("Perfil atualizado.")).to_be_visible()
    expect(page.locator("#sidebar-user-name")).to_have_text("Maria Souza")
    expect(page.locator("h1")).to_have_text("Minha conta")
    expect(page.get_by_text("Maria Souza · Usuário")).to_be_visible()
    expect(salvar).to_be_disabled()

    page.goto("/app")  # saudação da Home
    expect(page.get_by_role("heading", name="Olá, Maria Souza")).to_be_visible()

    page.goto("/app/account")  # persistiu no servidor
    expect(page.get_by_label("Nome de exibição")).to_have_value("Maria Souza")
    expect(page.get_by_role("radio", name="Violeta")).to_have_attribute("aria-checked", "true")

    # limpar volta ao usuário de login
    page.get_by_label("Nome de exibição").fill("")
    page.get_by_role("radio", name="Laranja").click()
    page.get_by_role("button", name="Salvar alterações").click()
    expect(page.locator("#sidebar-user-name")).to_have_text(username)


def test_nome_malicioso_aparece_como_texto_em_todo_lugar(account):
    _, page, _ = account
    page.get_by_label("Nome de exibição").fill(XSS)
    page.get_by_role("button", name="Salvar alterações").click()
    expect(page.get_by_text("Perfil atualizado.")).to_be_visible()

    expect(page.locator("#sidebar-user-name")).to_have_text(XSS)
    page.goto("/app")
    expect(page.get_by_role("heading", name=f"Olá, {XSS}")).to_be_visible()
    assert page.locator("img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_campo_de_nome_limita_a_60_caracteres(account):
    _, page, _ = account
    page.get_by_label("Nome de exibição").fill("x" * 80)
    expect(page.get_by_label("Nome de exibição")).to_have_value("x" * 60)
    expect(page.get_by_text("60/60")).to_be_visible()


def test_medidor_de_forca_e_requisitos_da_senha(account):
    _, page, _ = account
    page.get_by_role("tab", name="Segurança").click()
    nova = page.locator("#new-password")
    botao = page.get_by_role("button", name="Salvar nova senha")

    nova.fill("abc")
    expect(page.locator("#strength-label")).to_have_text("Força: Muito fraca")
    nova.fill("abcdefgh")
    expect(page.locator("#strength-label")).to_have_text("Força: Fraca")
    nova.fill("Abcdef12")
    expect(page.locator("#strength-label")).to_have_text("Força: Média")
    nova.fill("Abcdef123456!")
    expect(page.locator("#strength-label")).to_have_text("Força: Forte")

    page.locator("#confirm-password").fill("diferente")
    expect(page.get_by_text("As senhas não conferem.")).to_be_visible()
    page.locator("#current-password").fill(PASSWORD)
    expect(botao).to_be_disabled()

    page.locator("#confirm-password").fill("Abcdef123456!")
    expect(botao).to_be_enabled()

    nova.fill(PASSWORD)  # igual à atual
    page.locator("#confirm-password").fill(PASSWORD)
    expect(page.get_by_text("Diferente da senha atual")).to_be_visible()
    expect(botao).to_be_disabled()


def test_mostrar_e_ocultar_senha(account):
    _, page, _ = account
    page.get_by_role("tab", name="Segurança").click()
    campo = page.locator("#new-password")
    expect(campo).to_have_attribute("type", "password")
    page.get_by_role("button", name="Mostrar nova senha").click()
    expect(campo).to_have_attribute("type", "text")


def test_trocar_senha_com_senha_atual_errada_mostra_erro_e_com_certa_funciona(account, browser, base_url):
    context, page, username = account
    page.get_by_role("tab", name="Segurança").click()

    page.locator("#current-password").fill("senha-errada-123")
    page.locator("#new-password").fill("NovaSenhaForte123!")
    page.locator("#confirm-password").fill("NovaSenhaForte123!")
    page.get_by_role("button", name="Salvar nova senha").click()
    expect(page.get_by_role("alert")).to_contain_text("Senha atual incorreta")

    page.locator("#current-password").fill(PASSWORD)
    page.get_by_role("button", name="Salvar nova senha").click()
    expect(page.get_by_text("Senha alterada. Suas outras sessões foram encerradas.")).to_be_visible()
    expect(page.locator("#current-password")).to_have_value("")  # campos limpos

    assert page.context.request.get("/me").ok  # esta sessão continua válida (cookie novo)
    novo = browser.new_context(base_url=base_url)
    try:
        assert novo.request.post("/login", data={"username": username, "password": "NovaSenhaForte123!"}).ok
        assert novo.request.post("/login", data={"username": username, "password": PASSWORD}).status == 401
    finally:
        novo.close()


def test_encerrar_outras_sessoes_derruba_a_outra_e_mantem_esta(account, browser, base_url):
    _, page, username = account
    outra = browser.new_context(base_url=base_url)
    try:
        assert outra.request.post("/login", data={"username": username, "password": PASSWORD}).ok
        assert outra.request.get("/me").ok

        page.get_by_role("tab", name="Segurança").click()
        page.locator("#revoke-others").click()
        expect(page.get_by_text("Encerrar outras sessões?")).to_be_visible()
        page.get_by_role("button", name="Cancelar").click()
        assert outra.request.get("/me").ok  # cancelar não faz nada

        page.locator("#revoke-others").click()
        page.locator("#confirm-ok").click()
        expect(page.get_by_text("Outras sessões encerradas.")).to_be_visible()

        assert outra.request.get("/me").status == 401
        page.reload()
        expect(page.get_by_text("Trocar senha", exact=True)).to_be_visible()  # esta continua logada
    finally:
        outra.close()


def test_atividade_lista_acessos_e_destaca_falhas_sem_mostrar_ip(account, browser, base_url):
    _, page, username = account
    tentativa = browser.new_context(base_url=base_url)
    try:
        assert tentativa.request.post("/login", data={"username": username, "password": "errada-123"}).status == 401
    finally:
        tentativa.close()

    page.get_by_role("tab", name="Atividade").click()
    eventos = page.locator("#login-events li")
    expect(eventos).to_have_count(2)  # o login do fixture + a tentativa que falhou
    expect(eventos.first).to_contain_text("Falha")  # o mais novo primeiro
    expect(eventos.first).to_contain_text("Chrome")
    expect(page.get_by_text("Houve 1 tentativa de acesso que falhou")).to_be_visible()
    expect(page.get_by_text("nunca o endereço IP")).to_be_visible()
    assert re.search(r"\d+\.\d+\.\d+\.\d+", page.locator("#login-events").inner_text()) is None


def test_admin_aparece_como_administrador(logged_in_admin):
    page = logged_in_admin
    page.goto("/app/account")
    expect(page.get_by_text("Administrador", exact=True).first).to_be_visible()


def test_no_celular_nao_vaza_na_horizontal(account):
    _, page, _ = account
    page.set_viewport_size({"width": 390, "height": 800})
    for aba in ["", "?aba=seguranca", "?aba=atividade"]:
        page.goto(f"/app/account{aba}")
        page.wait_for_timeout(500)
        m = page.evaluate("({sw: document.documentElement.scrollWidth, iw: innerWidth})")
        assert m["sw"] <= m["iw"], (aba, m)
