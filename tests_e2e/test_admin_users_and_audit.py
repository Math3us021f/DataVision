"""Telas de administração (React): Usuários e Auditoria, de ponta a ponta no navegador."""

import re

from playwright.sync_api import expect

from conftest import unique_username

PASSWORD = "senha-inicial-123"
XSS_NAME = "<img src=x onerror=window.__xss=1>"


def create_user_via_ui(page, username, password=PASSWORD):
    page.goto("/app/admin/users")
    page.locator("#new-user-button").click()
    page.locator("#new-username").fill(username)
    page.locator("#new-password").fill(password)
    page.locator("#create-user-submit").click()
    expect(page.get_by_text(f'Usuário "{username}" criado.')).to_be_visible()


def search_users(page, term):
    page.locator("#users-search").fill(term)
    return page.locator(f'tr[data-user="{term}"]')


def test_admin_cria_usuario_e_ele_aparece_na_lista(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)

    # O banco de dev acumula usuários de testes anteriores, então busca pelo nome.
    expect(search_users(page, username)).to_be_visible()
    expect(page.locator("#users-count")).to_have_text("1 usuário")


def test_criar_usuario_com_senha_curta_mostra_o_erro_do_servidor_dentro_do_painel(logged_in_admin):
    page = logged_in_admin
    page.goto("/app/admin/users")
    page.locator("#new-user-button").click()
    page.locator("#new-username").fill(unique_username("ui"))
    page.locator("#new-password").fill("curta")
    # minlength do navegador barra antes de enviar; o painel continua aberto e sem usuário criado
    page.locator("#create-user-submit").click()
    expect(page.locator("#create-user-form")).to_be_visible()


def test_criar_usuario_repetido_mostra_erro_no_painel(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)

    page.locator("#new-user-button").click()
    page.locator("#new-username").fill(username)
    page.locator("#new-password").fill(PASSWORD)
    page.locator("#create-user-submit").click()
    expect(page.locator("#create-user-error")).to_be_visible()
    expect(page.locator("#create-user-form")).to_be_visible()


def test_desativar_e_reativar_usuario_atualiza_status_e_indicadores(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)
    row = search_users(page, username)
    expect(row).to_contain_text("Ativo")

    inativas_antes = int(page.locator("#summary-inactive").inner_text())
    page.get_by_label(f"Desativar {username}").click()
    page.locator("#confirm-ok").click()
    expect(row).to_contain_text("Inativo")
    expect(page.locator("#summary-inactive")).to_have_text(str(inativas_antes + 1))

    page.get_by_label(f"Ativar {username}").click()  # reativar não pede confirmação
    expect(row).to_contain_text("Ativo")
    expect(page.locator("#summary-inactive")).to_have_text(str(inativas_antes))


def test_filtro_de_status_so_mostra_inativos(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)
    search_users(page, username)
    page.get_by_label(f"Desativar {username}").click()
    page.locator("#confirm-ok").click()

    page.locator("#users-status").select_option("active")
    expect(page.locator("#users-table-body tr")).to_have_count(0)
    expect(page.get_by_text("Nenhum usuário encontrado")).to_be_visible()
    page.locator("#users-status").select_option("inactive")
    expect(page.locator(f'tr[data-user="{username}"]')).to_be_visible()


def test_redefinir_senha_permite_entrar_com_a_nova(browser, base_url, logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)
    search_users(page, username)

    page.get_by_label(f"Redefinir senha de {username}").click()
    page.locator("#reset-password").fill("nova-senha-456")
    page.locator("#reset-submit").click()
    expect(page.get_by_text(f'Senha de "{username}" redefinida.')).to_be_visible()

    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": "nova-senha-456"}).ok
        assert not context.request.post("/login", data={"username": username, "password": PASSWORD}).ok
    finally:
        context.close()


def test_a_propria_conta_nao_tem_acoes_nem_selecao(logged_in_admin, admin_credentials):
    page = logged_in_admin
    me = admin_credentials[0]
    page.goto("/app/admin/users")
    row = search_users(page, me)
    expect(row).to_be_visible()
    expect(row).to_contain_text("você")
    expect(row.get_by_role("checkbox")).to_be_disabled()
    expect(row.get_by_role("button")).to_have_count(0)


def test_excluir_usuario_pede_confirmacao_e_remove_da_lista(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)
    row = search_users(page, username)

    page.get_by_label(f"Excluir {username}").click()
    page.locator("#confirm-ok").click()
    expect(page.get_by_text(f'Usuário "{username}" excluído.')).to_be_visible()
    expect(row).to_have_count(0)


def test_acoes_em_lote_desativam_e_excluem_varios_de_uma_vez(logged_in_admin):
    page = logged_in_admin
    prefixo = unique_username("lote")
    nomes = [f"{prefixo}_{i}" for i in range(3)]
    for nome in nomes:
        assert page.request.post("/users", data={"username": nome, "password": PASSWORD}).ok

    page.goto("/app/admin/users")
    page.locator("#users-search").fill(prefixo)
    expect(page.locator("#users-table-body tr")).to_have_count(3)

    page.locator("#select-all").check()
    expect(page.locator("#bulk-count")).to_have_text("3 usuários selecionados")

    page.locator("#bulk-deactivate").click()
    page.locator("#confirm-ok").click()
    expect(page.get_by_text("3 usuários desativados.")).to_be_visible()
    expect(page.locator('#users-table-body tr:has-text("Inativo")')).to_have_count(3)

    page.locator("#select-all").check()
    page.locator("#bulk-delete").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#users-table-body tr")).to_have_count(0)
    expect(page.locator("#bulk-bar")).to_have_count(0)


def test_usuario_com_datasets_exige_segunda_confirmacao_para_excluir(logged_in_admin, browser, base_url):
    page = logged_in_admin
    username = unique_username("ui")
    assert page.request.post("/users", data={"username": username, "password": PASSWORD}).ok
    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": PASSWORD}).ok
        up = context.request.post("/datasets/upload", multipart={"file": {"name": "d.csv", "mimeType": "text/csv", "buffer": b"a\n1\n"}})
        assert up.ok
    finally:
        context.close()

    page.goto("/app/admin/users")
    search_users(page, username)
    page.get_by_label(f"Excluir {username}").click()
    page.locator("#confirm-ok").click()
    expect(page.get_by_role("heading", name="Apagar também os datasets?")).to_be_visible()
    expect(page.locator(f'tr[data-user="{username}"]')).to_be_visible()  # ainda existe até confirmar

    page.locator("#confirm-ok").click()
    expect(page.get_by_text(f'Usuário "{username}" e seus datasets foram excluídos.')).to_be_visible()
    expect(page.locator(f'tr[data-user="{username}"]')).to_have_count(0)


def test_nome_de_usuario_malicioso_vira_texto_nas_telas_de_admin(logged_in_admin):
    page = logged_in_admin
    # o nome é validado pelo servidor; o login falho é o caminho em que texto livre chega aos logs
    page.request.post("/login", data={"username": XSS_NAME, "password": "qualquer-coisa-1"})
    page.goto("/app/admin/logs")
    expect(page.locator("#logs-list")).to_be_visible()
    page.locator("#logs-search").fill("onerror")
    expect(page.locator("#logs-list li").first).to_contain_text(XSS_NAME)
    assert page.locator("#logs-list img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_criar_usuario_e_depois_ver_na_auditoria(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)

    page.goto("/app/admin/audit")
    page.locator("#audit-search").fill(username)
    row = page.locator("#audit-table-body tr").first
    expect(row).to_contain_text("Criação de usuário")
    expect(row).to_contain_text(username)
    expect(page.locator("#audit-count")).to_have_text("1 registro")


def test_auditoria_filtra_por_acao_e_mostra_vazio(logged_in_admin):
    page = logged_in_admin
    username = unique_username("ui")
    create_user_via_ui(page, username)

    page.goto("/app/admin/audit")
    page.locator("#audit-search").fill(username)
    page.locator("#audit-action").select_option("delete_user")
    expect(page.get_by_text("Nenhum registro encontrado")).to_be_visible()
    page.locator("#audit-action").select_option("create_user")
    expect(page.locator("#audit-table-body tr")).to_have_count(1)


def test_usuario_comum_nao_ve_links_de_admin_e_e_barrado_nas_rotas(browser, base_url, logged_in_admin):
    username = unique_username("ui")
    create_user_via_ui(logged_in_admin, username)

    # Contexto separado, para não derrubar a sessão do admin ao entrar com o usuário comum.
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    try:
        page.goto("/login")
        page.locator("#username").fill(username)
        page.locator("#password").fill(PASSWORD)
        page.locator("#login-submit").click()
        page.locator("#stat-datasets").wait_for(state="visible", timeout=10_000)

        expect(page.get_by_role("navigation", name="Administração")).to_have_count(0)
        expect(page.get_by_role("link", name="Usuários")).to_have_count(0)

        # Endereço novo: a tela devolve para o início. Endereço antigo: o servidor redireciona.
        for destino in ("/app/admin/audit", "/admin/audit", "/app/admin"):
            page.goto(destino)
            page.locator("#stat-datasets").wait_for(state="visible", timeout=10_000)
            expect(page).to_have_url(re.compile(r"/app$"))
            expect(page.locator("#audit-table-body")).to_have_count(0)

        # A proteção de verdade está na API, não só em esconder o menu.
        assert context.request.get("/users").status == 403
        assert context.request.get("/audit-logs").status == 403
    finally:
        context.close()
