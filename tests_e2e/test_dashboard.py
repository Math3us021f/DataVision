import pytest
from playwright.sync_api import expect

from conftest import unique_username

# Soma de valor = 750. Por região: Leste 375, Norte 225, Sul 150. Uma categoria de produto é um
# payload XSS de verdade: tem que aparecer como texto, nunca ser interpretada como HTML.
CSV = (
    b"data,regiao,produto,valor\n"
    b"2026-01-10,Sul,A,100\n2026-01-20,Sul,B,50\n2026-02-05,Norte,A,200\n"
    b"2026-02-15,Norte,<img src=x onerror=window.__xss=1>,25\n2026-03-01,Leste,B,300\n2026-03-10,Leste,A,75\n"
)


@pytest.fixture
def dashboard_page(browser, base_url, logged_in_admin):
    """Cria um usuário comum com um dataset já perfilado e abre o dashboard dele numa aba própria."""
    username, password = unique_username("dash"), "senha-inicial-123"
    created = logged_in_admin.request.post("/users", data={"username": username, "password": password})
    assert created.ok

    context = browser.new_context(base_url=base_url)
    try:
        assert context.request.post("/login", data={"username": username, "password": password}).ok
        upload = context.request.post(
            "/datasets/upload",
            multipart={"file": {"name": "vendas.csv", "mimeType": "text/csv", "buffer": CSV}},
        )
        assert upload.ok
        dataset_id = upload.json()["id"]
        assert context.request.post(f"/datasets/{dataset_id}/profile").ok

        page = context.new_page()
        page.goto(f"/meus-datasets/{dataset_id}/dashboard")
        yield page
    finally:
        context.close()


def test_dashboard_mostra_kpi_e_graficos_e_trata_payload_como_texto(dashboard_page):
    page = dashboard_page
    expect(page.locator(".kpi-value")).to_have_text("750")
    expect(page.locator(".chart-box canvas")).to_have_count(3)  # linha + 2 pizzas
    expect(page.locator(".widget__title")).to_have_text([
        "Soma de valor",
        "Soma de valor por data (dia)",
        "Soma de valor por regiao",
        "Soma de valor por produto",
    ])

    assert page.locator(".widgets-grid img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_filtro_global_recalcula_os_graficos(dashboard_page):
    page = dashboard_page
    expect(page.locator(".kpi-value")).to_have_text("750")

    page.locator("#add-filter").click()
    selects = page.locator(".filter-row select")
    selects.nth(0).select_option("valor")
    selects.nth(1).select_option("gte")
    page.locator(".filter-row input").fill("100")

    expect(page.locator(".kpi-value")).to_have_text("600")  # 100 + 200 + 300
    expect(page.locator(".widget__meta").first).to_have_text("3 linha(s) consideradas")


def test_personalizar_agregacao_do_kpi(dashboard_page):
    page = dashboard_page
    kpi_card = page.locator(".widget").first
    kpi_card.locator("summary").click()
    kpi_card.locator("select[id$='-agg']").select_option("mean")

    expect(page.locator(".kpi-value")).to_have_text("125")  # 750 / 6
    expect(kpi_card.locator(".widget__title")).to_have_text("Média de valor")
