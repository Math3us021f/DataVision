"""Rotas de página: a casca da interface (React). O servidor só entrega o HTML e exige sessão; os dados vêm
da API, que valida permissões em cada rota. O roteamento interno (/app/...) é feito no navegador."""

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect


def _react_shell() -> HttpResponse:
    index = settings.REACT_INDEX
    if not index.is_file():
        return HttpResponse(
            "Interface ainda não gerada. Rode: docker compose --profile frontend run --rm frontend",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    return FileResponse(open(index, "rb"), content_type="text/html")


def login_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return HttpResponseRedirect("/app")
    return _react_shell()


def app_shell(request: HttpRequest, path: str = "") -> HttpResponse:
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/login")
    return _react_shell()
