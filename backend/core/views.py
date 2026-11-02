"""Rotas de página: a casca da interface (React) e os endereços antigos, que redirecionam para a interface nova.

O servidor só entrega o HTML e exige sessão; os dados vêm da API, que valida permissões em cada rota. O roteamento
interno (/app/...) é feito no navegador."""

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import ensure_csrf_cookie

ADMIN_PAGES = {"users", "metrics", "logs", "files", "audit"}


def _react_shell() -> HttpResponse:
    index = settings.REACT_INDEX
    if not index.is_file():
        return HttpResponse(
            "Interface ainda não gerada. Rode: docker compose --profile frontend run --rm frontend",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    return FileResponse(open(index, "rb"), content_type="text/html")


@ensure_csrf_cookie  # a tela de login recebe o cookie csrftoken, que o React devolve em X-CSRFToken
def login_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return HttpResponseRedirect("/app")
    return _react_shell()


@ensure_csrf_cookie
def app_shell(request: HttpRequest, path: str = "") -> HttpResponse:
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/login")
    return _react_shell()


# Endereços antigos continuam existindo (favoritos, links salvos) e levam para a interface nova. Sem sessão, vão
# para o login como qualquer outra página.
def _to_new_ui(request: HttpRequest, destination: str) -> HttpResponse:
    return HttpResponseRedirect(destination if request.user.is_authenticated else "/login")


def home_redirect(request: HttpRequest) -> HttpResponse:
    return _to_new_ui(request, "/app")


def datasets_redirect(request: HttpRequest) -> HttpResponse:
    return _to_new_ui(request, "/app/datasets")


def dataset_dashboard_redirect(request: HttpRequest, dataset_id: int) -> HttpResponse:
    return _to_new_ui(request, f"/app/datasets/{dataset_id}/dashboard")


def account_redirect(request: HttpRequest) -> HttpResponse:
    return _to_new_ui(request, "/app/account")


def _admin_destination(request: HttpRequest, destination: str) -> HttpResponse:
    # Só controla a navegação; a proteção real está na API (AdminAuth), que barra qualquer chamada de quem não é admin.
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/login")
    if not request.user.is_admin:
        return HttpResponseRedirect("/app")
    return HttpResponseRedirect(destination)


def admin_index(request: HttpRequest) -> HttpResponse:
    return _admin_destination(request, "/app/admin/users")


def admin_page(request: HttpRequest, page: str) -> HttpResponse:
    if page not in ADMIN_PAGES:
        raise Http404("Página não encontrada")
    return _admin_destination(request, f"/app/admin/{page}")
