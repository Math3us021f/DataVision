"""Fixtures compartilhadas dos testes de interface (Playwright).

Roda num serviço Docker separado (`e2e`, profile `test`), contra a aplicação
real já de pé (serviço `app`), pela rede interna do Compose — nunca contra
mocks. Ver `docs/escopo_e_roteiro.md` (Etapa 5 do plano de interface).
"""

import os
import uuid

import pytest
from playwright.sync_api import APIRequestContext

# O Django exige o token CSRF (cookie csrftoken → cabeçalho X-CSRFToken) em toda requisição que altera dados. O
# navegador de verdade o envia pelo código do React; as chamadas diretas dos testes (page.request, context.request)
# passam por este adaptador, que faz o mesmo: lê o cookie e o devolve no cabeçalho.


def _csrf_token(request_context: APIRequestContext) -> str | None:
    for cookie in request_context.storage_state()["cookies"]:
        if cookie["name"] == "csrftoken":
            return cookie["value"]
    return None


def _with_csrf(method_name: str) -> None:
    original = getattr(APIRequestContext, method_name)

    def wrapper(self, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        if not any(name.lower() == "x-csrftoken" for name in headers):
            token = _csrf_token(self)
            if token is None:
                self.get("/login")  # a tela de entrada entrega o cookie csrftoken
                token = _csrf_token(self)
            if token:
                headers["X-CSRFToken"] = token
        kwargs["headers"] = headers
        return original(self, url, **kwargs)

    setattr(APIRequestContext, method_name, wrapper)


for _method in ("post", "put", "patch", "delete"):
    _with_csrf(_method)


@pytest.fixture(scope="session")
def base_url() -> str:
    # Sobrescreve a fixture base_url do pytest-playwright: por padrão ela exige
    # a flag --base-url na linha de comando, mas aqui o alvo é sempre o serviço
    # 'app' da rede do Compose (ou localhost, se alguém rodar fora do Docker).
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture
def admin_credentials() -> tuple[str, str]:
    return os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"]


def unique_username(prefix: str = "e2e") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def logged_in_admin(page, admin_credentials):
    """Faz login como admin pela UI de verdade e devolve a página já na home."""
    username, password = admin_credentials
    page.goto("/login")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#login-submit").click()
    # Espera um elemento que só existe depois do login (nunca a URL: o padrão glob
    # "**/" do Playwright combina até com "/login", mascarando falha de login).
    page.locator("#stat-datasets").wait_for(state="visible", timeout=10_000)  # Home da interface nova
    return page
