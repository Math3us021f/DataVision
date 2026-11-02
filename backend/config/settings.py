"""Configuração do Django. Tudo que muda por ambiente vem de variáveis de ambiente (as mesmas do .env do projeto)."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------- ambiente ----------

APP_ENV = os.environ.get("APP_ENV", "development")
PRODUCTION = APP_ENV == "production"
DEBUG = not PRODUCTION  # DEBUG mostra detalhes de erro: só fora de produção

SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,app,django,testserver").split(",") if h.strip()]

# ---------- aplicações ----------

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "ninja",  # a documentação interativa (/docs, só fora de produção) usa os modelos dele
    "accounts",
    "audit",
    "datasets",
    "analytics",
    "adminpanel",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # entrega a interface (React) gerada, em /static/app/
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.session_policy.SessionPolicyMiddleware",  # inatividade, limite de 8 h e versão da sessão
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Não há páginas HTML próprias: a interface é toda o React (o servidor só entrega a casca e a API em JSON).
# Os modelos abaixo existem só para os pacotes instalados (a documentação interativa da API).
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True, "OPTIONS": {}}]

# ---------- banco ----------


def _database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": 60,  # reaproveita a conexão entre requisições (o FastAPI abria uma nova a cada uma)
        # O usuário da aplicação não pode criar bancos (de propósito): o banco de teste já existe (db-init) e é reaproveitado.
        "TEST": {"NAME": f"{parsed.path.lstrip('/')}_test"},
    }


DATABASES = {"default": _database_from_url(os.environ["DJANGO_DATABASE_URL"])}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- usuários e senhas ----------

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

# ---------- sessão e cookies ----------

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "session"  # o mesmo nome do FastAPI: o React e os testes não percebem a troca
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_AGE = 60 * 60 * 8  # limite absoluto de 8 h desde o login, mesmo com atividade
# Sem nenhuma atividade da pessoa por este tempo, a sessão deixa de valer (ver accounts/session_policy.py). O
# navegador lê este valor em GET /me para avisar antes; quem encerra de verdade é o servidor.
SESSION_IDLE_TIMEOUT_SECONDS = 15 * 60
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"
# O React lê o cookie csrftoken e devolve o valor no cabeçalho X-CSRFToken (por isso não é HttpOnly).
CSRF_COOKIE_HTTPONLY = False

# ---------- cabeçalhos de segurança ----------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
# O Django envia Cross-Origin-Opener-Policy por padrão, mas os navegadores a ignoram (com erro no console) fora de HTTPS
# ou localhost. Só vale ligar quando o acesso é por HTTPS (SESSION_COOKIE_SECURE=true).
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin" if SESSION_COOKIE_SECURE else None
X_FRAME_OPTIONS = "DENY"

# ---------- arquivos estáticos (a interface React gerada) ----------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Em desenvolvimento o Compose monta o resultado do build do React em ./static_src/app, que vira /static/app/.
STATICFILES_DIRS = [BASE_DIR / "static_src"] if (BASE_DIR / "static_src").exists() else []
REACT_INDEX = Path(os.environ.get("REACT_INDEX", BASE_DIR / "static_src" / "app" / "index.html"))
WHITENOISE_USE_FINDERS = DEBUG  # em produção só serve o que o collectstatic coletou
WHITENOISE_AUTOREFRESH = DEBUG

# ---------- internacionalização ----------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = False
USE_TZ = True

# ---------- logs ----------

LOG_DIR = Path(os.environ.get("LOG_DIR", BASE_DIR / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"padrao": {"format": "%(asctime)s %(levelname)s %(message)s"}},
    "handlers": {
        # Gira sozinho: 5 MB por arquivo, 5 antigos guardados (igual ao FastAPI).
        "arquivo": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "padrao",
        },
        "console": {"class": "logging.StreamHandler", "formatter": "padrao"},
    },
    "loggers": {
        "datavision": {"handlers": ["arquivo", "console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
