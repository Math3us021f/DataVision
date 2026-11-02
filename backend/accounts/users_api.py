"""Gestão de usuários (só administradores)."""

from typing import Literal

from ninja import Query, Router, Schema, Status
from pydantic import Field

from accounts import services
from accounts.auth import AdminAuth

router = Router(tags=["usuários"])
admin = AdminAuth()


class CreateUserIn(Schema):
    username: str
    password: str
    is_admin: bool = False
    email: str | None = Field(default=None, max_length=254)


class UserOut(Schema):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    email_masked: str | None = None  # nunca o e-mail inteiro


class UserPage(Schema):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UsersSummaryOut(Schema):
    total: int
    active: int
    inactive: int
    admins: int


class UserListParams(Schema):
    search: str = Field(default="", max_length=100)
    status: Literal["all", "active", "inactive"] = "all"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class UpdateActiveIn(Schema):
    is_active: bool


class ResetPasswordIn(Schema):
    new_password: str


class UpdateEmailIn(Schema):
    email: str | None = Field(default=None, max_length=254)  # vazio ou nulo remove o e-mail


@router.post("/users", auth=admin, response={201: UserOut}, summary="Cria um usuário")
def create_user(request, data: CreateUserIn):
    return Status(201, services.create_user(request.auth, data.username, data.password, data.is_admin, data.email))


# "summary" vem antes das rotas com {user_id} (e estas só aceitam números), para nunca serem confundidos.
@router.get("/users/summary", auth=admin, response=UsersSummaryOut, summary="Totais de contas")
def users_summary(request):
    return services.users_summary()


@router.get("/users", auth=admin, response=UserPage, summary="Lista usuários (busca, filtro e paginação)")
def list_users(request, params: Query[UserListParams]):
    return services.list_users_page(params.search, params.status, params.page, params.page_size)


@router.patch("/users/{int:user_id}", auth=admin, response=UserOut, summary="Ativa ou desativa um usuário")
def set_user_active(request, user_id: int, data: UpdateActiveIn):
    return services.set_user_active(request.auth, user_id, data.is_active)


@router.delete("/users/{int:user_id}", auth=admin, response={204: None}, summary="Exclui um usuário")
def delete_user(request, user_id: int, force: bool = False):
    services.delete_user(request.auth, user_id, force)
    return Status(204, None)


@router.put("/users/{int:user_id}/password", auth=admin, response={204: None}, summary="Redefine a senha de outro usuário")
def reset_password(request, user_id: int, data: ResetPasswordIn):
    services.reset_user_password(request.auth, user_id, data.new_password)
    return Status(204, None)


@router.patch("/users/{int:user_id}/email", auth=admin, response=UserOut, summary="Define ou remove o e-mail de outra conta")
def set_user_email(request, user_id: int, data: UpdateEmailIn):
    """Sem confirmação por e-mail; a pessoa é avisada no sistema. O administrador não altera o próprio e-mail por aqui."""
    return services.set_user_email(request.auth, user_id, data.email)
