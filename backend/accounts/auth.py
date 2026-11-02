"""Autenticação das rotas da API (Django Ninja).

O Ninja marca as rotas como isentas de CSRF e deixa a verificação para a classe de autenticação. Por isso TODAS as
rotas usam uma destas classes, até as públicas (login): sem isso, uma página de outro site poderia mandar um
formulário para o nosso login em nome da pessoa.
"""

from ninja.errors import HttpError
from ninja.security import APIKeyCookie

from accounts.session_policy import NOT_AUTHENTICATED_DETAIL, PROBLEM_DETAILS


class CsrfProtected(APIKeyCookie):
    """Rotas públicas (ex.: login): não exigem sessão, mas exigem o token CSRF nas requisições que alteram dados."""

    param_name = "csrftoken"

    def authenticate(self, request, key):
        return True


class SessionAuth(APIKeyCookie):
    """Exige uma sessão válida. A política (inatividade, 8 h, versão) já rodou no middleware; aqui só se lê o resultado
    para devolver 401 com a mensagem certa."""

    param_name = "session"

    def authenticate(self, request, key):
        if request.user.is_authenticated:
            return request.user
        detail = PROBLEM_DETAILS.get(getattr(request, "session_problem", None), NOT_AUTHENTICATED_DETAIL)
        raise HttpError(401, detail)


class AdminAuth(SessionAuth):
    """Exige sessão válida E que o usuário seja administrador (negação por padrão: comum recebe 403)."""

    def authenticate(self, request, key):
        user = super().authenticate(request, key)
        if not user.is_admin:
            raise HttpError(403, "Requer privilégio de administrador")
        return user
