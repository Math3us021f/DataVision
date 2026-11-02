from playwright.sync_api import expect

from conftest import unique_username


def create_user_via_ui(page, username, password="senha-inicial-123"):
    page.goto("/admin/users")
    page.locator('[data-drawer-open="create-user-drawer"]').click()
    page.locator("#new-username").fill(username)
    page.locator("#new-password").fill(password)
    page.locator("#create-user-submit").click()
    expect(page.locator(".toast--success")).to_be_visible()


def test_admin_cria_usuario_e_ele_aparece_na_lista(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)

    # O banco de dev acumula usuários de testes anteriores (ver docs/testes_manuais.md),
    # então o usuário recém-criado pode não estar na 1ª página sem busca.
    page.locator("#users-search").fill(username)
    page.wait_for_timeout(500)  # a busca tem debounce de 300ms no JS
    expect(page.locator("#users-table-body")).to_contain_text(username)


def test_criar_usuario_e_depois_ver_na_auditoria(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)

    page.goto("/admin/audit")
    page.locator("#audit-search").fill(username)
    page.wait_for_timeout(500)  # a busca tem debounce de 300ms no JS

    row = page.locator("#audit-table-body tr").first
    expect(row).to_contain_text("Criação de usuário")
    expect(row).to_contain_text(username)


def test_usuario_comum_nao_ve_links_de_admin(browser, base_url, logged_in_admin):
    username = unique_username("ui")
    password = "senha-inicial-123"
    create_user_via_ui(logged_in_admin, username, password)

    # Aba separada (contexto novo), para não derrubar a sessão do admin
    # logado em `logged_in_admin` ao entrar com o usuário comum.
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    try:
        page.goto("/login")
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)
        page.locator("#login-submit").click()
        page.locator(".sidebar__username").wait_for(state="visible", timeout=10_000)

        expect(page.locator('a[href="/admin/users"]')).to_have_count(0)
        expect(page.locator('a[href="/admin/audit"]')).to_have_count(0)

        # Proteção real está no backend, não só escondendo o link: acesso direto
        # a uma rota de admin redireciona para a home, não mostra a página.
        page.goto("/admin/audit")
        page.locator(".sidebar__username").wait_for(state="visible", timeout=10_000)
        expect(page.locator("#audit-table-body")).to_have_count(0)
    finally:
        context.close()
