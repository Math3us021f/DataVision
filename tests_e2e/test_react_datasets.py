"""Nova interface (React) — tela de Datasets: lista, envio, perfil, exclusão, busca e paginação."""

import re

import pytest
from playwright.sync_api import expect

from conftest import unique_username

# 4 linhas, 1 duplicada (Ana,30,SP aparece duas vezes), 3 colunas, 1 valor ausente em idade.
CSV = b"nome,idade,cidade\nAna,30,SP\nBruno,25,RJ\nCarla,,SP\nAna,30,SP\n"
XSS = "<img src=x onerror=window.__xss=1>"
XSS_CSV = f"{XSS},valor\n{XSS},1\nnormal,2\n".encode()


def upload(context, name, content=CSV, profile=False):
    response = context.request.post(
        "/datasets/upload", multipart={"file": {"name": name, "mimeType": "text/csv", "buffer": content}}
    )
    assert response.ok, response.text()
    dataset_id = response.json()["id"]
    if profile:
        assert context.request.post(f"/datasets/{dataset_id}/profile").ok
    return dataset_id


def new_user_context(browser, base_url, admin_page):
    username, password = unique_username("ds"), "senha-inicial-123"
    assert admin_page.request.post("/users", data={"username": username, "password": password}).ok
    context = browser.new_context(base_url=base_url)
    assert context.request.post("/login", data={"username": username, "password": password}).ok
    return context


@pytest.fixture
def ctx(browser, base_url, logged_in_admin):
    context = new_user_context(browser, base_url, logged_in_admin)
    yield context
    context.close()


@pytest.fixture
def datasets_page(ctx):
    """Usuário comum com um dataset perfilado e um pendente, já na tela de Datasets."""
    upload(ctx, "vendas.csv", profile=True)
    upload(ctx, "pendente.csv")
    page = ctx.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto("/app/datasets")
    expect(page.locator("tr[data-dataset-id]")).to_have_count(2)
    return page


def row(page, name):
    return page.locator("tr[data-dataset-id]", has=page.get_by_text(name, exact=True))


def test_anonimo_e_redirecionado_para_o_login(page):
    page.goto("/app/datasets")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_lista_mostra_nome_tamanho_status_e_resumo(datasets_page):
    page = datasets_page
    expect(row(page, "vendas.csv").get_by_text("Perfilado", exact=True)).to_be_visible()
    expect(row(page, "pendente.csv").get_by_text("Pendente", exact=True)).to_be_visible()
    expect(row(page, "vendas.csv")).to_contain_text(f"{len(CSV)} B")
    expect(row(page, "vendas.csv").get_by_role("link", name="Dashboard")).to_have_attribute("href", re.compile(r"/meus-datasets/\d+/dashboard$"))

    expect(page.locator("#summary-total")).to_have_text("2")
    expect(page.locator("#summary-profiled")).to_have_text("1")
    expect(page.get_by_role("link", name="Datasets", exact=True)).to_have_attribute("aria-current", "page")


def test_envio_pelo_seletor_aparece_na_lista_e_atualiza_o_resumo(datasets_page):
    page = datasets_page
    page.locator("#file-input").set_input_files({"name": "novo.csv", "mimeType": "text/csv", "buffer": CSV})

    expect(page.get_by_text('"novo.csv" enviado.')).to_be_visible()
    expect(row(page, "novo.csv").get_by_text("Pendente", exact=True)).to_be_visible()
    expect(page.locator("#summary-total")).to_have_text("3")


def test_formato_invalido_e_arquivo_grande_demais_sao_recusados_na_hora(datasets_page):
    page = datasets_page
    page.locator("#file-input").set_input_files({"name": "foto.png", "mimeType": "image/png", "buffer": b"x"})
    expect(page.get_by_role("alert")).to_contain_text("formato não permitido")

    page.locator("#file-input").set_input_files({"name": "enorme.csv", "mimeType": "text/csv", "buffer": b"a" * 10_000_001})
    expect(page.get_by_role("alert")).to_contain_text("maior que 10 MB")
    expect(page.locator("tr[data-dataset-id]")).to_have_count(2)  # nada foi enviado


def test_servidor_recusa_conteudo_que_nao_bate_com_a_extensao(datasets_page):
    page = datasets_page
    page.locator("#file-input").set_input_files({"name": "falso.xlsx", "mimeType": "application/octet-stream", "buffer": b"isto nao e um zip"})
    expect(page.locator("#upload-queue")).to_contain_text("não corresponde ao formato")
    expect(page.locator("tr[data-dataset-id]")).to_have_count(2)


def test_busca_filtra_por_nome_e_avisa_quando_nao_acha(datasets_page):
    page = datasets_page
    page.get_by_label("Buscar por nome").fill("pend")
    expect(page.locator("tr[data-dataset-id]")).to_have_count(1)
    expect(row(page, "pendente.csv")).to_be_visible()

    page.get_by_label("Buscar por nome").fill("nada-assim")
    expect(page.locator("tr[data-dataset-id]")).to_have_count(0)
    expect(page.get_by_text("Nenhum resultado")).to_be_visible()


def test_paginacao_quando_ha_mais_de_8_datasets(ctx):
    for i in range(9):
        upload(ctx, f"arquivo{i}.csv")
    page = ctx.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto("/app/datasets")
    expect(page.locator("tr[data-dataset-id]")).to_have_count(8)
    expect(page.get_by_text("Mostrando 1–8 de 9")).to_be_visible()

    page.get_by_label("Próxima página").click()
    expect(page.locator("tr[data-dataset-id]")).to_have_count(1)
    expect(page.get_by_label("Próxima página")).to_be_disabled()


def test_perfil_mostra_numeros_exatos_amostra_e_um_grafico_por_coluna(datasets_page):
    page = datasets_page
    row(page, "vendas.csv").get_by_role("button", name="Perfil").click()

    resumo = page.locator("#profile-summary dd")
    expect(resumo).to_have_text(["4", "1", "3"])  # linhas, duplicadas, colunas
    expect(page.get_by_text("4 de 4 linha(s)")).to_be_visible()
    expect(page.locator("dialog[open] thead th", has_text="nome")).to_be_visible()
    expect(page.locator("dialog[open] tbody td", has_text="Bruno")).to_be_visible()
    expect(page.locator("article")).to_have_count(3)
    expect(page.locator("article canvas")).to_have_count(3)
    idade = page.locator("article").filter(has=page.get_by_role("heading", name="idade", exact=True))
    expect(idade).to_contain_text("Ausentes: 1 (25.0%)")
    expect(idade).to_contain_text("Mediana")

    page.keyboard.press("Escape")
    expect(page.locator("#profile-summary")).to_be_hidden()


def test_dataset_pendente_pede_para_calcular_e_depois_vira_perfilado(datasets_page):
    page = datasets_page
    row(page, "pendente.csv").get_by_role("button", name="Perfil").click()
    expect(page.get_by_text("Ainda não perfilado")).to_be_visible()

    page.get_by_role("button", name="Calcular perfil").click()
    expect(page.locator("#profile-summary dd")).to_have_text(["4", "1", "3"])
    expect(page.get_by_text("Perfil calculado.")).to_be_visible()
    expect(page.get_by_role("button", name="Recalcular")).to_be_visible()

    page.keyboard.press("Escape")
    expect(row(page, "pendente.csv").get_by_text("Perfilado", exact=True)).to_be_visible()
    expect(page.locator("#summary-profiled")).to_have_text("2")


def test_exclusao_pede_confirmacao_cancelar_mantem_confirmar_remove(datasets_page):
    page = datasets_page
    page.get_by_label("Excluir pendente.csv").click()
    expect(page.get_by_text("Excluir dataset?")).to_be_visible()
    page.get_by_role("button", name="Cancelar").click()
    expect(page.locator("tr[data-dataset-id]")).to_have_count(2)

    page.get_by_label("Excluir pendente.csv").click()
    page.locator("#confirm-ok").click()
    expect(page.get_by_text('"pendente.csv" excluído.')).to_be_visible()
    expect(page.locator("tr[data-dataset-id]")).to_have_count(1)
    expect(page.locator("#summary-total")).to_have_text("1")


def test_nome_de_arquivo_e_conteudo_maliciosos_aparecem_como_texto(ctx):
    upload(ctx, f"{XSS}.csv", content=XSS_CSV, profile=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto("/app/datasets")
    linha = page.locator("tr[data-dataset-id]").first
    expect(linha).to_contain_text(f"{XSS}.csv")

    linha.get_by_role("button", name="Perfil").click()
    expect(page.locator("#profile-summary")).to_be_visible()
    expect(page.locator("dialog[open] thead th", has_text=XSS).first).to_be_visible()  # cabeçalho da amostra
    page.keyboard.press("Escape")

    page.get_by_label(f"Excluir {XSS}.csv").click()
    expect(page.get_by_text("Excluir dataset?")).to_be_visible()

    assert page.locator("img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_link_do_inicio_para_datasets_navega_dentro_do_app_sem_recarregar(ctx):
    upload(ctx, "vendas.csv")
    page = ctx.new_page()
    page.set_viewport_size({"width": 1600, "height": 900})
    page.goto("/app")
    expect(page.locator("#stat-datasets")).to_be_visible()
    page.evaluate("window.__marcador = 'continua'")

    page.get_by_role("link", name=re.compile("Datasets enviados")).click()
    expect(page).to_have_url(re.compile(r"/app/datasets$"))
    expect(page.locator("#datasets-table")).to_be_visible()
    assert page.evaluate("window.__marcador") == "continua"  # a página não foi recarregada
