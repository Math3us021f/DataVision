"""Ferramentas comuns dos testes: cliente JSON, relógio que anda, caixa de e-mails falsa e limpeza do limite de login."""

import json as json_lib
import re
import time

import pytest
from django.test import Client

from accounts import login_flow, session_policy
from core import rate_limit

PASSWORD = "senha-123-x"


class ApiClient(Client):
    """Cliente de teste do Django que aceita `json=` (como o TestClient do FastAPI) nos métodos que enviam corpo."""

    def _with_json(self, method, path, data, json, extra):
        if json is not None:
            return method(path, json_lib.dumps(json), content_type="application/json", **extra)
        return method(path, data, content_type="application/json", **extra) if data is not None else method(path, **extra)

    def post(self, path, data=None, json=None, **extra):
        if json is None:
            return super().post(path, data if data is not None else {}, **extra)
        return super().post(path, json_lib.dumps(json), content_type="application/json", **extra)

    def patch(self, path, data=None, json=None, **extra):
        return self._with_json(super().patch, path, data, json, extra)

    def put(self, path, data=None, json=None, **extra):
        return self._with_json(super().put, path, data, json, extra)

    def delete(self, path, data=None, json=None, **extra):
        return self._with_json(super().delete, path, data, json, extra)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    rate_limit._failed_attempts.clear()
    yield
    rate_limit._failed_attempts.clear()


@pytest.fixture
def client():
    return ApiClient()


@pytest.fixture
def clock(monkeypatch):
    """Relógio da política de sessão: `clock["t"] += 600` anda 10 minutos."""
    state = {"t": time.time()}
    monkeypatch.setattr(session_policy, "_now", lambda: state["t"])
    return state


@pytest.fixture
def outbox(monkeypatch):
    """Captura os e-mails em vez de enviar: lista de (destinatário, assunto, corpo)."""
    sent = []
    monkeypatch.setattr(login_flow, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def code_of(message) -> str:
    return re.search(r"\b(\d{6})\b", message[2]).group(1)


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """O hash de senha de verdade (PBKDF2, 600 mil voltas) é lento de propósito; nos testes usa-se um rápido. O
    PBKDF2 continua habilitado só para verificar o hash descartável do login de usuário inexistente."""
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
