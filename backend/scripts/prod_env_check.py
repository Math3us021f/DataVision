"""Confere, dentro do contêiner de produção, o que não pode estar errado: modo, hosts e cabeçalhos.

Uso (ensaio): docker compose --env-file ... -f compose.prod.yaml exec -T app python manage.py shell < backend/scripts/prod_env_check.py
"""

from django.conf import settings
from django.test import Client

print("APP_ENV production:", settings.PRODUCTION, "| DEBUG:", settings.DEBUG)
print("ALLOWED_HOSTS:", settings.ALLOWED_HOSTS)
cliente = Client(HTTP_HOST=settings.ALLOWED_HOSTS[0])
for caminho in ("/health", "/docs", "/openapi.json", "/login"):
    resposta = cliente.get(caminho)
    print(f"{caminho:15s} {resposta.status_code}")
print("CSP presente:", "Content-Security-Policy" in cliente.get("/health"))
