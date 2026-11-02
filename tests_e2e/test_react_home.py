"""Nova interface (React) em /app — Home. Roda contra o build real servido pelo FastAPI."""

import re

import pytest
from playwright.sync_api import expect

from conftest import unique_username

CSV = b"a,b\n1,2\n"
XSS_NAME = "<img src=x onerror=window.__xss=1>.csv"


def metrics(page):
    return page.evaluate(
        "({sh: document.documentElement.scrollHeight, ih: innerHeight, sw: document.documentElement.scrollWidth, iw: innerWidth})"
    )


def open_app(page, width=1920, height=950):
    page.set_viewport_size({"width": width, "height": height})
    page.goto("/app")
    expect(page.locator("#stat-datasets")).to_be_visible()


@pytest.fixture
def common_user_page(browser, base_url, logged_in_admin):
    """Usuário comum com um dataset de nome malicioso; devolve a aba dele já em /app."""
    username, password = unique_username("react"), "senha-inicial-123"
    assert logged_in_admin.request.post("/users", data={"username": username, "password": password}).ok

    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": password}).ok
        upload = context.request.post(
            "/datasets/upload", multipart={"file": {"name": XSS_NAME, "mimeType": "text/csv", "buffer": CSV}}
        )
        assert upload.ok
        page = context.new_page()
        page.goto("/app")
        yield page
    finally:
        context.close()


def test_anonimo_e_redirecionado_para_o_login(page):
    page.goto("/app")
    expect(page).to_have_url(re.compile(r"/login$"))
    page.goto("/app/qualquer/coisa")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_home_do_admin_mostra_indicadores_graficos_e_listas_sem_erros(logged_in_admin):
    page = logged_in_admin
    erros = []
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))

    open_app(page)
    for stat in ["#stat-datasets", "#stat-storage", "#stat-profiled", "#stat-users", "#stat-all-datasets", "#stat-cpu", "#stat-memory"]:
        expect(page.locator(stat)).to_be_visible()
    expect(page.locator("#stat-cpu")).to_contain_text("%")
    expect(page.locator("canvas")).to_have_count(2)  # uploads por dia + status dos datasets
    expect(page.locator("#recent-datasets li").first).to_be_visible()
    expect(page.locator("#recent-audit li").first).to_be_visible()
    expect(page.locator("#legend-profiled")).to_be_visible()
    assert erros == []


@pytest.mark.parametrize("size", [(1920, 950), (1366, 640), (1280, 720)])
def test_home_cabe_numa_tela_sem_rolagem_da_pagina(logged_in_admin, size):
    open_app(logged_in_admin, *size)
    logged_in_admin.wait_for_timeout(500)
    m = metrics(logged_in_admin)
    assert m["sh"] <= m["ih"], f"a página rola em {size}: {m}"
    assert m["sw"] <= m["iw"], f"a página vaza na horizontal em {size}: {m}"


def test_no_celular_nao_vaza_na_horizontal_e_o_menu_desliza(logged_in_admin):
    page = logged_in_admin
    open_app(page, 390, 800)
    m = metrics(page)
    assert m["sw"] <= m["iw"], m
    expect(page.locator("#sidebar-collapse")).to_be_hidden()
    page.locator("#menu-toggle").click()
    expect(page.locator("#sidebar")).to_be_in_viewport()


def test_menu_recolhe_e_lembra_a_escolha(logged_in_admin):
    page = logged_in_admin
    open_app(page, 1600, 800)
    botao = page.locator("#sidebar-collapse")
    expect(botao).to_have_attribute("aria-expanded", "true")
    botao.click()
    expect(botao).to_have_attribute("aria-label", "Expandir menu")
    page.wait_for_function("document.querySelector('#sidebar').getBoundingClientRect().width < 100")

    page.reload()  # lembra ao recarregar
    expect(page.locator("#sidebar-collapse")).to_have_attribute("aria-expanded", "false")

    page.locator("#sidebar-collapse").click()  # expande de volta (deixa o estado limpo)
    expect(page.locator("#sidebar-collapse")).to_have_attribute("aria-expanded", "true")
    page.wait_for_function("document.querySelector('#sidebar').getBoundingClientRect().width > 200")


def test_tema_alterna_persiste_e_vale_na_interface_atual(logged_in_admin):
    page = logged_in_admin
    open_app(page)
    html = page.locator("html")
    escuro_antes = "dark" in (html.get_attribute("class") or "")
    page.get_by_role("button", name="Alternar tema claro/escuro").click()
    expect(html).to_have_class(re.compile(r"^(?!.*\bdark\b)") if escuro_antes else re.compile(r"\bdark\b"))

    page.reload()
    assert ("dark" in (html.get_attribute("class") or "")) != escuro_antes

    page.goto("/app/admin/users")  # a escolha vale em todas as telas, inclusive as de administração
    assert ("dark" in (page.locator("html").get_attribute("class") or "")) != escuro_antes

    page.goto("/app")
    page.get_by_role("button", name="Alternar tema claro/escuro").click()  # restaura


def test_usuario_comum_nao_ve_o_que_e_do_admin_e_nome_malicioso_vira_texto(common_user_page):
    page = common_user_page
    expect(page.locator("#stat-datasets")).to_be_visible()

    for admin_only in ["#stat-users", "#stat-cpu", "#stat-memory", "#recent-audit"]:
        expect(page.locator(admin_only)).to_have_count(0)
    expect(page.locator('a[href="/admin/users"]')).to_have_count(0)

    item = page.locator("#recent-datasets li").first
    expect(item).to_contain_text(XSS_NAME)  # aparece como texto literal
    assert page.locator("#recent-datasets img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_sair_encerra_a_sessao(logged_in_admin):
    page = logged_in_admin
    open_app(page)
    page.locator("#logout-button").click()
    expect(page).to_have_url(re.compile(r"/login$"))
    page.goto("/app")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_rota_desconhecida_dentro_do_app_mostra_pagina_nao_encontrada(logged_in_admin):
    page = logged_in_admin
    page.goto("/app/nao-existe")
    expect(page.get_by_text("Página não encontrada")).to_be_visible()
    page.get_by_role("link", name="Voltar ao início").click()
    expect(page.locator("#stat-datasets")).to_be_visible()
