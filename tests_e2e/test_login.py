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
    expect(logged_in_admin).to_have_url(re.compile(r"/$"))
    expect(logged_in_admin.locator(".sidebar__username")).to_have_text(username)


def test_logout_volta_para_login(logged_in_admin):
    logged_in_admin.locator("#logout-button").click()
    logged_in_admin.wait_for_url("**/login")
    expect(logged_in_admin.locator("#login-form")).to_be_visible()


def test_acesso_a_home_sem_sessao_redireciona_para_login(page):
    page.goto("/")
    page.wait_for_url("**/login")
    expect(page.locator("#login-form")).to_be_visible()
