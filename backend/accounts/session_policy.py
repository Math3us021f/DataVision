"""Política da sessão: expira por inatividade (15 min), tem limite absoluto (8 h) e cai quando a `session_version`
do usuário sobe (senha trocada ou "encerrar outras sessões").

O Django guarda a sessão no banco e manda ao navegador só o cookie `session`. Além do usuário, esta sessão leva
três anotações nossas: `start` (quando entrou), `act` (última atividade) e `v` (versão da sessão do usuário).
Um middleware as confere a cada requisição. Quem decide é sempre o servidor; o navegador só avisa antes.
"""

import time

from django.conf import settings
from django.contrib.auth import login, logout

IDLE_DETAIL = "Sessão encerrada por inatividade"
EXPIRED_DETAIL = "Sessão expirada"
ENDED_DETAIL = "Sessão encerrada"
NOT_AUTHENTICATED_DETAIL = "Não autenticado"

PROBLEM_DETAILS = {"idle": IDLE_DETAIL, "expired": EXPIRED_DETAIL, "ended": ENDED_DETAIL}

# Requisições automáticas (telas que se atualizam sozinhas) mandam este cabeçalho e NÃO contam como atividade:
# sem isso, deixar a tela de Métricas aberta manteria a sessão viva para sempre.
BACKGROUND_REQUEST_HEADER = "X-Background-Request"

# Páginas e arquivos estáticos não renovam a sessão: a tela carregada logo em seguida chama a API, que renova.
_NEVER_RENEW_PREFIXES = ("/login", "/app", "/static")


def _now() -> float:
    return time.time()  # função à parte para os testes poderem "andar o relógio"


def start_session(request, user) -> None:
    """Entrega a sessão depois de a pessoa passar por tudo (senha e, se houver, código)."""
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")  # troca a chave da sessão e o token CSRF
    now = _now()
    request.session["start"] = now
    request.session["act"] = now
    request.session["v"] = user.session_version


class SessionPolicyMiddleware:
    """Vem depois do AuthenticationMiddleware: se a sessão deixou de valer, desconecta e anota o motivo em
    `request.session_problem` ("idle", "expired" ou "ended"), para a API responder com a mensagem certa."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.session_problem = None
        user = request.user
        if user.is_authenticated:
            session = request.session
            now = _now()
            # Sessões sem as anotações (criadas por fora do nosso login) são inicializadas na primeira vez.
            start = session.setdefault("start", now)
            last_activity = session.setdefault("act", now)
            version = session.setdefault("v", user.session_version)

            if now - start > settings.SESSION_COOKIE_AGE:
                problem = "expired"
            elif now - last_activity > settings.SESSION_IDLE_TIMEOUT_SECONDS:
                problem = "idle"
            elif version != user.session_version:
                problem = "ended"
            else:
                problem = None

            if problem:
                logout(request)  # apaga a sessão do banco e o cookie; request.user vira anônimo
                request.session_problem = problem
            elif self._counts_as_activity(request):
                session["act"] = now  # renova o prazo: o cookie é reenviado com o horário novo
        return self.get_response(request)

    @staticmethod
    def _counts_as_activity(request) -> bool:
        if request.headers.get(BACKGROUND_REQUEST_HEADER) is not None:
            return False
        return not request.path.startswith(_NEVER_RENEW_PREFIXES)
