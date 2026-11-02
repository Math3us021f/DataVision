"""Fixtures compartilhadas dos testes de interface (Playwright).

Roda num serviço Docker separado (`e2e`, profile `test`), contra a aplicação
real já de pé (serviço `app`), pela rede interna do Compose — nunca contra
mocks. Ver `docs/escopo_e_roteiro.md` (Etapa 5 do plano de interface).
"""

import os
import uuid

import pytest


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
    page.locator(".sidebar__username").wait_for(state="visible", timeout=10_000)
    return page
