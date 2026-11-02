"""Esqueleto do backend Django: saúde, cabeçalhos de segurança, casca do React, modelo de usuário e configuração."""

import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

User = get_user_model()
BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------- saúde e cabeçalhos ----------


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "DataVision"}


@pytest.mark.parametrize("path", ["/health", "/login", "/app"])
def test_cabecalhos_de_seguranca_em_todas_as_respostas(client, path):
    headers = client.get(path).headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "same-origin"


def test_politica_de_conteudo_so_aceita_a_propria_origem(client):
    csp = client.get("/login")["Content-Security-Policy"]
    diretivas = dict(parte.strip().split(" ", 1) for parte in csp.split(";") if parte.strip())
    assert diretivas["default-src"] == "'self'"
    assert diretivas["script-src"] == "'self'"  # sem 'unsafe-inline', 'unsafe-eval' nem domínios externos
    assert "'unsafe-eval'" not in csp and "http" not in csp
    assert diretivas["object-src"] == "'none'" and diretivas["frame-ancestors"] == "'none'"


def test_documentacao_interativa_fica_fora_da_politica_so_fora_de_producao(client):
    assert not settings.PRODUCTION  # estes testes rodam em desenvolvimento (o DEBUG é desligado pelo próprio pytest)
    docs = client.get("/docs")
    assert docs.status_code == 200 and "Content-Security-Policy" not in docs


def test_em_producao_nao_ha_docs_nem_debug():
    codigo = (
        "import django; django.setup(); from django.conf import settings; from config.api import api; "
        "print(settings.DEBUG, api.docs_url, api.openapi_url)"
    )
    env = {**os.environ, "APP_ENV": "production", "DJANGO_SETTINGS_MODULE": "config.settings"}
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, env=env, cwd=BACKEND_DIR)
    assert saida.stdout.split() == ["False", "None", "None"], saida.stderr


# ---------- casca da interface (React) ----------


def test_pagina_de_entrada_e_entregue_a_anonimo_e_o_app_exige_sessao(client):
    assert client.get("/login").status_code in (200, 503)  # 503 = interface ainda não gerada neste ambiente
    for caminho in ("/app", "/app/qualquer/coisa", "/app/admin/users"):
        resposta = client.get(caminho)
        assert resposta.status_code == 302 and resposta["Location"] == "/login", caminho


def test_casca_do_react_ou_aviso_de_que_nao_foi_gerada(client, settings, tmp_path):
    settings.REACT_INDEX = tmp_path / "nao-existe.html"
    sem_build = client.get("/login")
    assert sem_build.status_code == 503 and "docker compose --profile frontend" in sem_build.content.decode()

    index = tmp_path / "index.html"
    index.write_text('<!doctype html><div id="root"></div><script src="/static/app/assets/x.js"></script>', encoding="utf-8")
    settings.REACT_INDEX = index
    com_build = client.get("/login")
    assert com_build.status_code == 200 and b'<div id="root">' in b"".join(com_build.streaming_content)


@pytest.mark.django_db
def test_quem_esta_logado_vai_do_login_para_o_app_e_recebe_a_casca(client, settings, tmp_path):
    index = tmp_path / "index.html"
    index.write_text('<div id="root"></div>', encoding="utf-8")
    settings.REACT_INDEX = index
    client.force_login(User.objects.create_user("maria", "senha-123-x"))

    entrada = client.get("/login")
    assert entrada.status_code == 302 and entrada["Location"] == "/app"
    for caminho in ("/app", "/app/qualquer/coisa"):
        assert client.get(caminho).status_code == 200


def test_arquivos_gerados_do_react_sao_servidos_em_static_app(client):
    if not (BACKEND_DIR / "static_src" / "app" / "theme-init.js").exists():
        pytest.skip("interface não gerada neste ambiente")
    resposta = client.get("/static/app/theme-init.js")
    assert resposta.status_code == 200 and "datavision-theme" in b"".join(resposta.streaming_content).decode()


# ---------- usuário ----------


@pytest.mark.django_db
def test_senha_e_guardada_com_hash_e_confere():
    user = User.objects.create_user("ana", "senha-123-x")
    assert user.password != "senha-123-x" and "senha-123-x" not in user.password
    assert user.check_password("senha-123-x") and not user.check_password("outra")
    assert user.is_active and not user.is_admin and user.email is None and user.preferences == {}


@pytest.mark.django_db
def test_usuario_e_unico_e_email_e_unico_sem_diferenciar_maiusculas():
    User.objects.create_user("a", "senha-123-x", email="pessoa@exemplo.com")
    with pytest.raises(ValidationError):  # create_user valida antes de salvar
        User.objects.create_user("a", "senha-123-x")
    with pytest.raises(IntegrityError), transaction.atomic():
        User(username="b", email="PESSOA@exemplo.com").save()  # a regra também vale direto no banco


@pytest.mark.django_db
def test_varios_usuarios_sem_email_sao_permitidos():
    User.objects.create_user("sem1", "senha-123-x")
    User.objects.create_user("sem2", "senha-123-x")
    assert User.objects.filter(email__isnull=True).count() >= 2


@pytest.mark.django_db
def test_administrador_e_staff_e_tem_todas_as_permissoes():
    comum = User.objects.create_user("comum", "senha-123-x")
    admin = User.objects.create_superuser("chefe", "senha-123-x")
    assert admin.is_admin and admin.is_staff and admin.is_superuser and admin.has_perm("qualquer")
    assert not (comum.is_staff or comum.is_superuser or comum.has_perm("qualquer") or comum.has_module_perms("x"))
    comum.is_active = False
    admin.is_active = False
    assert not admin.has_perm("qualquer")  # conta desativada não tem permissão nenhuma


def test_senha_com_menos_de_8_caracteres_e_recusada():
    with pytest.raises(ValidationError):
        validate_password("curta")
    validate_password("longa-o-bastante")


# ---------- configuração ----------


def test_cookie_de_sessao_tem_o_mesmo_nome_e_as_mesmas_protecoes_do_fastapi():
    assert settings.SESSION_COOKIE_NAME == "session"
    assert settings.SESSION_COOKIE_HTTPONLY and settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_COOKIE_AGE == 8 * 3600
    assert settings.CSRF_COOKIE_HTTPONLY is False  # o React precisa ler o token para devolvê-lo no cabeçalho



@pytest.mark.django_db
def test_banco_e_postgres_e_responde():
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)


def test_logs_giram_ao_passar_de_5_mb():
    import logging

    handlers = [h for h in logging.getLogger("datavision").handlers if isinstance(h, RotatingFileHandler)]
    assert handlers and handlers[0].maxBytes == 5 * 1024 * 1024 and handlers[0].backupCount == 5


def test_nao_ha_segredo_no_codigo_de_configuracao():
    texto = (BACKEND_DIR / "config" / "settings.py").read_text(encoding="utf-8")
    assert 'os.environ["SECRET_KEY"]' in texto and "django-insecure" not in texto
