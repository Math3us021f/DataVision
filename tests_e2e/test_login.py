import re

from playwright.sync_api import expect


def test_login_com_senha_errada_mostra_erro(page, admin_credentials):
    username, _ = admin_credentials
    page.goto("/login")
    page.locator("#username").fill(username)
    page.locator("#password").fill("senha-definitivamente-errada")
    page.locator("#login-submit").click()

    expect(page.locator("#login-error")).to_be_visible()
    expect(page).to_have_url(re.compile(r"/login$"))


def test_login_com_senha_certa_vai_para_home(logged_in_admin, admin_credentials):
    username, _ = admin_credentials
    expect(logged_in_admin).to_have_url(re.compile(r"/app$"))
    # O menu mostra o nome de exibição, se a pessoa definiu um, ou o usuário de login.
    me = logged_in_admin.request.get("/me").json()
    assert me["username"] == username
    expect(logged_in_admin.locator("#sidebar-user-name")).to_have_text(me["display_name"] or username)


def test_logout_volta_para_login(logged_in_admin):
    logged_in_admin.locator("#logout-button").click()
    logged_in_admin.wait_for_url("**/login")
    expect(logged_in_admin.locator("#login-form")).to_be_visible()


def test_acesso_a_home_sem_sessao_redireciona_para_login(page):
    page.goto("/")
    page.wait_for_url("**/login")
    expect(page.locator("#login-form")).to_be_visible()


def test_login_sem_preencher_pede_usuario_e_senha_sem_chamar_o_servidor(page):
    chamadas = []
    page.on("request", lambda r: chamadas.append(r.url) if r.url.endswith("/login") and r.method == "POST" else None)
    page.goto("/login")
    page.locator("#login-submit").click()

    expect(page.locator("#login-error")).to_have_text("Preencha usuário e senha.")
    assert chamadas == []


def test_senha_errada_mostra_o_erro_sem_recarregar_a_pagina(page, admin_credentials):
    page.goto("/login")
    page.evaluate("window.__marcador = 'continua'")
    page.locator("#username").fill(admin_credentials[0])
    page.locator("#password").fill("senha-definitivamente-errada")
    page.locator("#password").press("Enter")  # Enter envia o formulário

    expect(page.locator("#login-error")).to_be_visible()
    assert page.evaluate("window.__marcador") == "continua"
    expect(page.locator("#login-submit")).to_be_enabled()


def test_botao_do_olho_mostra_e_oculta_a_senha(page):
    page.goto("/login")
    campo = page.locator("#password")
    expect(campo).to_have_attribute("type", "password")
    page.locator("#password-toggle").click()
    expect(campo).to_have_attribute("type", "text")
    expect(page.locator("#password-toggle")).to_have_attribute("aria-label", "Ocultar senha")
    page.locator("#password-toggle").click()
    expect(campo).to_have_attribute("type", "password")


def test_quem_ja_esta_logado_nao_ve_a_tela_de_login(logged_in_admin):
    logged_in_admin.goto("/login")
    expect(logged_in_admin).to_have_url(re.compile(r"/app$"))
