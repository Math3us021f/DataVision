"""Aviso e desconexão por inatividade, no navegador. O relógio da página é adiantado com page.clock
(esperar 15 minutos de verdade seria inviável); a contagem no SERVIDOR é testada em tests/test_session_idle.py."""

import re

from playwright.sync_api import expect

MIN = 60_000


def open_with_fake_clock(page):
    page.clock.install()
    page.goto("/app/datasets")
    expect(page.locator("#summary-total")).to_be_visible()
    expect(page.get_by_role("dialog", name="Você ainda está aí?")).to_have_count(0)


def test_aviso_aparece_antes_do_fim_do_prazo_e_continuar_mantem_a_sessao(logged_in_admin):
    page = logged_in_admin
    open_with_fake_clock(page)

    page.clock.fast_forward(14 * MIN + 5_000)  # 14 min parado
    dialogo = page.get_by_role("dialog", name="Você ainda está aí?")
    expect(dialogo).to_be_visible()
    segundos = int(page.locator("#idle-seconds").inner_text())
    assert 0 < segundos <= 60

    page.locator("#idle-continue").click()
    expect(dialogo).to_be_hidden()
    page.clock.fast_forward(5 * MIN)  # 5 min depois do "continuar": ainda dentro do novo prazo
    expect(dialogo).to_be_hidden()
    assert page.request.get("/me").ok
    expect(page).to_have_url(re.compile(r"/app/datasets$"))


def test_sem_confirmar_a_pessoa_e_desconectada_e_o_login_explica(logged_in_admin):
    page = logged_in_admin
    open_with_fake_clock(page)

    page.clock.fast_forward(14 * MIN + 5_000)
    expect(page.get_by_role("dialog", name="Você ainda está aí?")).to_be_visible()
    page.clock.fast_forward(MIN)  # o minuto do aviso passa sem resposta

    page.wait_for_url(re.compile(r"/login\?expired=idle$"))
    expect(page.locator("#login-notice")).to_contain_text("inatividade")
    assert page.request.get("/me").status == 401  # a sessão foi encerrada de verdade


def test_aviso_nao_fecha_com_esc_nem_clicando_no_fundo_e_movimento_do_mouse_nao_confirma(logged_in_admin):
    page = logged_in_admin
    open_with_fake_clock(page)
    page.clock.fast_forward(14 * MIN + 5_000)
    dialogo = page.get_by_role("dialog", name="Você ainda está aí?")
    expect(dialogo).to_be_visible()

    page.keyboard.press("Escape")
    page.mouse.click(5, 5)  # fora da janela (no fundo escurecido)
    page.mouse.move(300, 300)
    page.mouse.move(400, 350)
    expect(dialogo).to_be_visible()  # só os botões respondem


def test_sair_agora_desconecta_na_hora(logged_in_admin):
    page = logged_in_admin
    open_with_fake_clock(page)
    page.clock.fast_forward(14 * MIN + 5_000)
    page.locator("#idle-logout").click()
    page.wait_for_url(re.compile(r"/login\?expired=idle$"))
    assert page.request.get("/me").status == 401


def test_atividade_da_pessoa_adia_o_aviso(logged_in_admin):
    page = logged_in_admin
    open_with_fake_clock(page)

    page.clock.fast_forward(10 * MIN)
    page.mouse.move(200, 200)
    page.mouse.move(260, 240)  # atividade: o relógio de inatividade recomeça
    page.clock.fast_forward(10 * MIN)  # 10 min desde a atividade (20 desde o início)
    expect(page.get_by_role("dialog", name="Você ainda está aí?")).to_have_count(0)

    page.clock.fast_forward(4 * MIN + 5_000)  # agora 14 min parado
    expect(page.get_by_role("dialog", name="Você ainda está aí?")).to_be_visible()


def test_atualizacao_automatica_da_tela_de_metricas_nao_conta_como_atividade(logged_in_admin):
    page = logged_in_admin
    pedidos = []
    page.on(
        "request",
        lambda r: pedidos.append(r.headers.get("x-background-request")) if r.url.endswith("/metrics/system") else None,
    )
    page.goto("/app/admin/metrics")
    expect(page.locator("#cpu-value")).to_be_visible()
    page.wait_for_timeout(5_800)  # uma atualização automática (a cada 5 s)

    assert pedidos[0] is None  # a primeira busca, ao abrir a tela, é da pessoa
    assert len(pedidos) >= 2 and all(h == "1" for h in pedidos[1:])  # as automáticas não renovam a sessão


def test_login_mostra_o_motivo_so_quando_veio_por_tempo(page):
    page.goto("/login?expired=idle")
    expect(page.locator("#login-notice")).to_contain_text("inatividade")
    page.goto("/login?expired=time")
    expect(page.locator("#login-notice")).to_contain_text("tempo máximo")
    page.goto("/login")
    expect(page.locator("#login-notice")).to_have_count(0)
    page.goto("/login?expired=qualquer-coisa")  # valor desconhecido não vira texto na tela
    expect(page.locator("#login-notice")).to_have_count(0)
