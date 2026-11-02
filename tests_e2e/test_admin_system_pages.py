"""Telas de administração (React): Métricas, Logs e Arquivos."""

import re

import pytest
from playwright.sync_api import expect


def sem_erros_no_console(page):
    erros = []
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    return erros


# ---------- Métricas ----------


def test_metricas_mostram_cpu_memoria_disco_e_rede_com_o_aviso_de_escopo(logged_in_admin):
    page = logged_in_admin
    erros = sem_erros_no_console(page)
    page.goto("/app/admin/metrics")

    for bloco in ("cpu", "memory", "disk"):
        expect(page.locator(f"#{bloco}-value")).to_have_text(re.compile(r"^\d+(\.\d)?%$"))
        expect(page.locator(f"#{bloco}-detail")).not_to_be_empty()
    expect(page.locator("#net-sent")).to_have_text(re.compile(r"^\d+(\.\d)? (B|KB|MB|GB|TB)$"))
    expect(page.locator("#net-recv")).to_have_text(re.compile(r"^\d+(\.\d)? (B|KB|MB|GB|TB)$"))
    expect(page.locator("#metrics-scope")).to_contain_text("container")
    expect(page.locator("#metrics-updated")).to_contain_text("Atualizado às")
    assert erros == []


def test_metricas_atualizam_sozinhas(logged_in_admin):
    page = logged_in_admin
    chamadas = []
    page.on("request", lambda r: chamadas.append(r.url) if r.url.endswith("/metrics/system") else None)
    page.goto("/app/admin/metrics")
    expect(page.locator("#cpu-value")).to_be_visible()
    page.wait_for_timeout(5600)  # intervalo de atualização é de 5 s
    assert len(chamadas) >= 2


# ---------- Logs ----------


def test_logs_mostram_contagem_por_nivel_busca_e_filtro(logged_in_admin):
    page = logged_in_admin
    page.goto("/app/admin/logs")
    expect(page.locator("#logs-list li").first).to_be_visible()
    total = int(page.locator("#level-total").inner_text().replace(".", ""))
    assert total > 0

    page.locator("#logs-level").select_option("INFO")
    expect(page.locator("#logs-list li:not([data-level='INFO'])")).to_have_count(0)

    page.locator("#logs-search").fill("zzz-termo-que-nao-existe-zzz")
    expect(page.get_by_text("Nenhuma linha encontrada")).to_be_visible()
    expect(page.locator("#logs-summary")).to_contain_text("Mostrando 0 de")


def test_logs_limite_de_linhas_e_botao_atualizar(logged_in_admin):
    page = logged_in_admin
    page.goto("/app/admin/logs")
    expect(page.locator("#logs-list li").first).to_be_visible()

    with page.expect_response(lambda r: r.url.endswith("/logs/app?limit=50") and r.ok):
        page.locator("#logs-limit").select_option("50")
    with page.expect_response(lambda r: "/logs/app" in r.url and r.ok):
        page.locator("#logs-refresh").click()
    assert page.locator("#logs-list li").count() <= 50


# ---------- Arquivos ----------


def listar(page, caminho=""):
    resposta = page.request.get(f"/files?path={caminho}")
    assert resposta.ok
    return resposta.json()["entries"]


def test_explorador_navega_por_pastas_e_volta_pelo_caminho(logged_in_admin):
    page = logged_in_admin
    pastas = [e["name"] for e in listar(page) if e["is_dir"]]
    if not pastas:
        pytest.skip("a pasta data/ deste ambiente não tem subpastas")

    page.goto("/app/admin/files")
    expect(page.locator("#folder-count")).to_be_visible()
    page.locator('[data-entry="dir"]').first.click()
    breadcrumb = page.locator("#breadcrumb")
    expect(breadcrumb).to_contain_text("/")
    expect(page).to_have_url(re.compile(r"/app/admin/files$"))  # navegação interna, sem mudar o endereço

    breadcrumb.get_by_role("button", name="data").click()
    expect(breadcrumb).not_to_contain_text("/")


def test_explorador_abre_arquivo_de_texto_e_fecha(logged_in_admin):
    page = logged_in_admin
    textos = [e["name"] for e in listar(page) if not e["is_dir"] and e["name"].lower().endswith((".csv", ".txt", ".json")) and (e["size_bytes"] or 0) < 900_000]
    if not textos:
        pytest.skip("a pasta data/ deste ambiente não tem arquivo de texto")

    page.goto("/app/admin/files")
    page.get_by_role("button", name=textos[0]).click()
    expect(page.locator("#viewer-title")).to_contain_text(textos[0])
    expect(page.locator("#viewer-content")).not_to_be_empty()

    page.locator("#viewer-close").click()
    expect(page.locator("#viewer")).to_have_count(0)


def test_explorador_recusa_tipo_nao_permitido_com_mensagem(logged_in_admin):
    page = logged_in_admin
    binarios = [e["name"] for e in listar(page) if not e["is_dir"] and e["name"].lower().endswith(".xlsx")]
    if not binarios:
        pytest.skip("a pasta data/ deste ambiente não tem .xlsx")

    page.goto("/app/admin/files")
    page.get_by_role("button", name=binarios[0]).click()
    expect(page.locator("#viewer-error")).to_have_text("Tipo de arquivo não permitido")
    expect(page.locator("#viewer-content")).to_have_count(0)


def test_explorador_nao_sai_da_pasta_permitida_pela_api(logged_in_admin):
    page = logged_in_admin
    for caminho in ("..", "../src", "/etc", "..%2F..%2Fetc"):
        assert page.request.get(f"/files?path={caminho}").status == 400
    assert page.request.get("/files/content?path=../.env").status == 400
