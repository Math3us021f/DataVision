"""Cabeçalhos que dependem do ambiente: o COOP só vale (e só deve ser enviado) quando o acesso é por HTTPS."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def cabecalho_coop(secure: str) -> str:
    codigo = (
        "import django; django.setup(); from django.test import Client; "
        "print(Client().get('/health').headers.get('Cross-Origin-Opener-Policy'))"
    )
    env = {**os.environ, "SESSION_COOKIE_SECURE": secure, "DJANGO_SETTINGS_MODULE": "config.settings"}
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, env=env, cwd=BACKEND_DIR)
    return saida.stdout.strip().splitlines()[-1]


def test_coop_so_e_enviado_com_https():
    # Sem HTTPS o navegador a ignora e registra um erro no console; com HTTPS ela vale.
    assert cabecalho_coop("false") == "None"
    assert cabecalho_coop("true") == "same-origin"
