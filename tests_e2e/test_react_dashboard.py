"""Nova interface (React) — Dashboard do dataset: painel padrão, personalização, filtros, salvar e restaurar."""

import json
import re

import pytest
from playwright.sync_api import expect

from conftest import unique_username

PASSWORD = "senha-inicial-123"
XSS = "<img src=x onerror=window.__xss=1>"

# Soma de valor = 750. Por região: Leste 375, Norte 225, Sul 150. Média de valor = 125.
CSV = (
    b"data,regiao,produto,valor\n"
    b"2026-01-10,Sul,A,100\n2026-01-20,Sul,B,50\n2026-02-05,Norte,A,200\n"
    b"2026-02-15,Norte,B,25\n2026-03-01,Leste,B,300\n2026-03-10,Leste,A,75\n"
)
XSS_CSV = f"data,regiao,{XSS}\n2026-01-10,{XSS},10\n2026-02-10,Sul,20\n".encode()


def make_context(browser, base_url, admin_page):
    username = unique_username("dash")
    assert admin_page.request.post("/users", data={"username": username, "password": PASSWORD}).ok
    context = browser.new_context(base_url=base_url)
    assert context.request.post("/login", data={"username": username, "password": PASSWORD}).ok
    return context


def upload(context, name, content, profile=True):
    response = context.request.post("/datasets/upload", multipart={"file": {"name": name, "mimeType": "text/csv", "buffer": content}})
    assert response.ok
    dataset_id = response.json()["id"]
    if profile:
        assert context.request.post(f"/datasets/{dataset_id}/profile").ok
    return dataset_id


@pytest.fixture
def ctx(browser, base_url, logged_in_admin):
    context = make_context(browser, base_url, logged_in_admin)
    yield context
    context.close()


@pytest.fixture
def dash(ctx):
    """Aba aberta no dashboard de um dataset perfilado (e capturando as respostas de /query)."""
    dataset_id = upload(ctx, "vendas.csv", CSV)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1600, "height": 950})
    page.queries = []
    page.on(
        "response",
        lambda r: page.queries.append((json.loads(r.request.post_data or "{}"), r.json())) if r.url.endswith("/query") and r.ok else None,
    )
    page.goto(f"/app/datasets/{dataset_id}/dashboard")
    expect(page.locator("[data-widget]")).to_have_count(4)
    page.dataset_id = dataset_id
    return page


def widget(page, title):
    return page.locator("[data-widget]").filter(has=page.get_by_role("heading", name=title, exact=True))


def kpi(page):
    return page.locator("[data-kpi-value]").first


def open_settings(page, title):
    widget(page, title).get_by_label(f"Personalizar: {title}").click()


def test_anonimo_e_redirecionado_para_o_login(page):
    page.goto("/app/datasets/1/dashboard")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_painel_padrao_mostra_widgets_numeros_exatos_e_graficos(dash):
    page = dash
    expect(page.locator("[data-widget-title]")).to_have_text(
        ["Soma de valor", "Soma de valor por data (dia)", "Soma de valor por regiao", "Soma de valor por produto"]
    )
    expect(kpi(page)).to_have_text("750")
    expect(page.locator("[data-widget] canvas")).to_have_count(3)  # linha + 2 pizzas
    expect(page.locator("#dataset-name")).to_have_text("vendas.csv")
    expect(page.locator("#save-status")).to_have_text("Painel padrão — ainda não salvo")
    expect(page.get_by_role("link", name="Datasets", exact=True).first).to_be_visible()

    # o que cada gráfico recebe da API (números conferidos à mão)
    por_regiao = next(res for spec, res in page.queries if spec.get("dimension", {}) and spec["dimension"]["column"] == "regiao")
    assert dict(zip(por_regiao["categories"], por_regiao["series"][0]["data"])) == {"Leste": 375.0, "Norte": 225.0, "Sul": 150.0}


def test_filtro_global_recalcula_todos_os_graficos_e_remover_volta(dash):
    page = dash
    page.locator("#add-filter").click()
    filtro = page.locator("[data-filter]")
    filtro.get_by_label("Coluna do filtro").select_option("valor")
    filtro.get_by_label("Operador do filtro").select_option("gte")
    filtro.get_by_label("Valor do filtro").fill("100")

    expect(kpi(page)).to_have_text("600")  # 100 + 200 + 300
    expect(page.get_by_text("3 linha(s) consideradas").first).to_be_visible()
    expect(page.locator("#save-status")).to_have_text("Alterações não salvas")

    page.get_by_label("Remover filtro").click()
    expect(kpi(page)).to_have_text("750")


def test_filtro_em_lista_e_filtro_incompleto_e_ignorado(dash):
    page = dash
    page.locator("#add-filter").click()
    filtro = page.locator("[data-filter]")
    filtro.get_by_label("Coluna do filtro").select_option("regiao")
    filtro.get_by_label("Operador do filtro").select_option("in")
    expect(kpi(page)).to_have_text("750")  # sem valor ainda: ignorado, não zera o painel

    filtro.get_by_label("Valor do filtro").fill("Sul, Norte")
    expect(kpi(page)).to_have_text("375")  # 150 + 225


def test_personalizar_agregacao_tipo_e_coluna_respeitando_o_tipo_da_coluna(dash):
    page = dash
    open_settings(page, "Soma de valor")
    page.get_by_label("Agregação").select_option("mean")
    expect(kpi(page)).to_have_text("125")  # 750 / 6
    expect(page.get_by_role("heading", name="Média de valor", exact=True)).to_be_visible()

    page.get_by_label("Métrica (coluna)").select_option("regiao")
    opcoes = page.get_by_label("Agregação").locator("option").all_inner_texts()
    assert opcoes == ["Contagem", "Valores distintos"]  # coluna de texto: nada de soma/média
    expect(page.get_by_role("heading", name="Contagem de regiao", exact=True)).to_be_visible()

    open_settings(page, "Soma de valor por data (dia)")
    page.locator("[data-widget]").filter(has=page.get_by_role("heading", name="Soma de valor por data (dia)")).get_by_role("radio", name="Barras").click()
    expect(page.locator("[data-widget]").filter(has_text="por data").get_by_role("radio", name="Barras")).to_have_attribute("aria-checked", "true")


def test_agrupar_datas_por_mes_muda_os_pontos_do_grafico(dash):
    page = dash
    open_settings(page, "Soma de valor por data (dia)")
    with page.expect_response(lambda r: r.url.endswith("/query") and '"month"' in (r.request.post_data or "")) as resposta:
        page.get_by_label("Agrupar datas por").select_option("month")
    expect(page.get_by_role("heading", name="Soma de valor por data (mês)")).to_be_visible()
    mensal = resposta.value.json()
    assert mensal["categories"] == ["2026-01", "2026-02", "2026-03"]
    assert mensal["series"][0]["data"] == [150.0, 225.0, 375.0]


def test_adicionar_e_remover_graficos_com_limite_de_12(dash):
    page = dash
    page.locator("#add-widget").click()
    expect(page.locator("[data-widget]")).to_have_count(5)

    page.get_by_label("Remover: Soma de valor por produto").click()
    expect(page.locator("[data-widget]")).to_have_count(4)

    for _ in range(8):
        page.locator("#add-widget").click()
    expect(page.locator("[data-widget]")).to_have_count(12)
    page.locator("#add-widget").click()
    expect(page.get_by_text("Limite de 12 gráficos por dashboard.")).to_be_visible()
    expect(page.locator("[data-widget]")).to_have_count(12)


def test_salvar_recarregar_mantem_personalizacao_e_restaurar_descarta(dash):
    page = dash
    open_settings(page, "Soma de valor")
    page.get_by_label("Agregação").select_option("mean")
    page.locator("#add-filter").click()
    filtro = page.locator("[data-filter]")
    filtro.get_by_label("Coluna do filtro").select_option("valor")
    filtro.get_by_label("Operador do filtro").select_option("gte")
    filtro.get_by_label("Valor do filtro").fill("100")
    expect(kpi(page)).to_have_text("200")  # média de 100, 200, 300

    page.locator("#save-dashboard").click()
    expect(page.get_by_text("Dashboard salvo.")).to_be_visible()
    expect(page.locator("#save-status")).to_contain_text("Salvo em")

    page.reload()
    expect(kpi(page)).to_have_text("200")
    expect(page.get_by_role("heading", name="Média de valor", exact=True)).to_be_visible()
    expect(page.get_by_label("Coluna do filtro")).to_have_value("valor")
    expect(page.get_by_label("Valor do filtro")).to_have_value("100")

    page.locator("#reset-dashboard").click()
    page.locator("#confirm-ok").click()
    expect(page.get_by_text("Painel padrão restaurado.")).to_be_visible()
    expect(kpi(page)).to_have_text("750")
    expect(page.locator("[data-filter]")).to_have_count(0)

    page.reload()
    expect(kpi(page)).to_have_text("750")
    expect(page.locator("#save-status")).to_have_text("Painel padrão — ainda não salvo")


def test_dataset_nao_perfilado_oferece_calcular_e_continua(ctx):
    dataset_id = upload(ctx, "pendente.csv", CSV, profile=False)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1600, "height": 950})
    page.goto(f"/app/datasets/{dataset_id}/dashboard")
    expect(page.get_by_text("Este dataset ainda não foi perfilado")).to_be_visible()

    page.get_by_role("button", name="Calcular perfil e continuar").click()
    expect(kpi(page)).to_have_text("750")
    expect(page.locator("[data-widget]")).to_have_count(4)


def test_dataset_inexistente_ou_de_outro_usuario_mostra_nao_encontrado(browser, base_url, logged_in_admin, ctx):
    dataset_id = upload(ctx, "dele.csv", CSV)  # dataset do usuário A
    outro = make_context(browser, base_url, logged_in_admin)  # usuário B
    try:
        page = outro.new_page()
        page.goto(f"/app/datasets/{dataset_id}/dashboard")
        expect(page.get_by_text("Dataset não encontrado")).to_be_visible()
        page.goto("/app/datasets/99999999/dashboard")
        expect(page.get_by_text("Dataset não encontrado")).to_be_visible()
    finally:
        outro.close()




def test_nome_de_coluna_e_categoria_maliciosos_viram_texto(ctx):
    dataset_id = upload(ctx, "xss.csv", XSS_CSV)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1600, "height": 950})
    page.goto(f"/app/datasets/{dataset_id}/dashboard")
    expect(page.locator("[data-widget]").first).to_be_visible()

    expect(page.get_by_role("heading", name=f"Soma de {XSS}", exact=True)).to_be_visible()  # título como texto
    open_settings(page, f"Soma de {XSS}")
    expect(page.get_by_label("Métrica (coluna)")).to_contain_text(XSS)  # nas opções do seletor também
    page.locator("#add-filter").click()
    page.wait_for_timeout(600)

    assert page.locator("img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_botao_dashboard_da_lista_navega_dentro_do_app_e_menu_continua_em_datasets(ctx):
    upload(ctx, "vendas.csv", CSV)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1600, "height": 950})
    page.goto("/app/datasets")
    page.evaluate("window.__marcador = 'continua'")
    page.get_by_role("link", name="Dashboard").first.click()

    expect(page).to_have_url(re.compile(r"/app/datasets/\d+/dashboard$"))
    expect(kpi(page)).to_have_text("750")
    assert page.evaluate("window.__marcador") == "continua"  # sem recarregar a página
    expect(page.locator("#sidebar").get_by_role("link", name="Datasets", exact=True)).to_have_attribute("aria-current", "page")


def test_no_celular_nao_vaza_na_horizontal(dash):
    page = dash
    page.set_viewport_size({"width": 390, "height": 800})
    page.locator("#add-filter").click()
    page.wait_for_timeout(500)
    m = page.evaluate("({sw: document.documentElement.scrollWidth, iw: innerWidth})")
    assert m["sw"] <= m["iw"], m
