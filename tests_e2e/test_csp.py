"""A política de segurança de conteúdo (CSP) não pode quebrar nenhuma tela: nenhuma violação, nenhum erro."""

import re

from playwright.sync_api import expect

TELAS = [
    "/app",
    "/app/datasets",
    "/app/account",
    "/app/admin/users",
    "/app/admin/audit",
    "/app/admin/metrics",
    "/app/admin/logs",
    "/app/admin/files",
]

ESPIAO = """
window.__violacoes = [];
document.addEventListener("securitypolicyviolation", (e) => window.__violacoes.push(e.violatedDirective + " " + e.blockedURI));
"""


def test_nenhuma_tela_viola_a_politica_de_conteudo(logged_in_admin):
    page = logged_in_admin
    erros = []
    page.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.add_init_script(ESPIAO)

    for url in TELAS:
        page.goto(url)
        page.wait_for_timeout(900)
        assert page.evaluate("window.__violacoes") == [], url
    assert erros == []


def test_resposta_traz_a_politica_e_o_tema_continua_funcionando_sem_script_inline(logged_in_admin):
    page = logged_in_admin
    resposta = page.goto("/app")
    assert "script-src 'self'" in resposta.headers["content-security-policy"]
    # o arquivo externo de tema roda antes de desenhar e obedece à escolha salva
    for escolhido in ("dark", "light"):
        page.evaluate(f"localStorage.setItem('datavision-theme', '{escolhido}')")
        page.reload()
        page.wait_for_selector("#sidebar")
        assert page.evaluate("document.documentElement.classList.contains('dark')") is (escolhido == "dark")
    page.evaluate("localStorage.removeItem('datavision-theme')")


def test_script_injetado_pela_pagina_e_bloqueado_pelo_navegador(logged_in_admin):
    page = logged_in_admin
    page.goto("/app")
    page.add_init_script(ESPIAO)
    page.reload()
    executou = page.evaluate(
        """() => new Promise((resolve) => {
            window.__xss = 0;
            const s = document.createElement("script");
            s.textContent = "window.__xss = 1";   // script inline: a política proíbe
            document.head.append(s);
            setTimeout(() => resolve(window.__xss), 200);
        })"""
    )
    assert executou == 0
    assert any(v.startswith("script-src") for v in page.evaluate("window.__violacoes"))


def test_login_tambem_funciona_com_a_politica(page):
    page.add_init_script(ESPIAO)
    page.goto("/login")
    expect(page.locator("#login-form")).to_be_visible()
    assert page.evaluate("window.__violacoes") == []
    assert re.search(r"script-src 'self'", page.request.get("/login").headers["content-security-policy"])
