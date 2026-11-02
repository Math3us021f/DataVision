"""Regras de negócio da gestão de usuários (só administradores): criação, busca, ativação, exclusão, senha e e-mail.

As rotas em accounts/users_api.py ficam só com a camada HTTP (validação da entrada e códigos de status) e chamam
estas funções. Cada alteração roda numa transação: se algo falhar no meio, nada fica pela metade.
"""

import logging
from typing import Literal

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from ninja.errors import HttpError

from accounts.models import User
from accounts.notifications import create_notification
from accounts.passwords import validate_new_password
from accounts.verification import InvalidEmailError, mask_email, normalize_email
from audit.models import AuditLog
from audit.services import log_action
from datasets.services import delete_dataset

logger = logging.getLogger("datavision")

MAX_USERNAME_LENGTH = 150


def public_user(user: User) -> dict:
    """O que a API mostra de um usuário: nunca o e-mail inteiro, só a versão mascarada."""
    return {
        "id": user.pk,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "email_masked": mask_email(user.email),
    }


def clean_email(raw: str) -> str:
    try:
        return normalize_email(raw)
    except InvalidEmailError as exc:
        raise HttpError(400, str(exc)) from exc


def ensure_email_free(email: str, except_user_id: int | None = None) -> None:
    if User.objects.filter(email__iexact=email).exclude(pk=except_user_id).exists():
        raise HttpError(409, "Este e-mail já está em uso por outra conta.")


def get_user_or_404(user_id: int) -> User:
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise HttpError(404, "Usuário não encontrado")
    return user


def create_user(admin: User, username: str, password: str, is_admin: bool, email: str | None = None) -> dict:
    username = username.strip()
    if not username:
        raise HttpError(400, "Informe o nome de usuário.")
    if len(username) > MAX_USERNAME_LENGTH:
        raise HttpError(400, f"O nome de usuário pode ter no máximo {MAX_USERNAME_LENGTH} caracteres.")
    validate_new_password(password)
    email = clean_email(email) if email and email.strip() else None

    if User.objects.filter(username=username).exists():
        raise HttpError(409, "Nome de usuário já existe")
    if email:
        ensure_email_free(email)

    try:
        with transaction.atomic():
            user = User(username=username, is_admin=is_admin, email=email)
            user.set_password(password)
            user.save()
            log_action(admin, AuditLog.Action.CREATE_USER, target=user, details=f"com e-mail {mask_email(email)}" if email else None)
    except IntegrityError:  # duas criações iguais ao mesmo tempo: a restrição do banco decide
        raise HttpError(409, "Nome de usuário já existe")

    logger.info("Usuário criado: id=%s username=%r por admin_id=%s", user.pk, username, admin.pk)
    return public_user(user)


def list_users_page(search: str, status_filter: Literal["all", "active", "inactive"], page: int, page_size: int) -> dict:
    users = User.objects.all()
    if search.strip():
        users = users.filter(username__icontains=search.strip())  # escapa % e _: busca literal
    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    total = users.count()
    page_users = users.order_by("id")[(page - 1) * page_size : page * page_size]
    return {"items": [public_user(u) for u in page_users], "total": total, "page": page, "page_size": page_size}


def users_summary() -> dict:
    return User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        admins=Count("id", filter=Q(is_admin=True)),
    )


def set_user_active(admin: User, user_id: int, is_active: bool) -> dict:
    if user_id == admin.pk and not is_active:
        raise HttpError(400, "Você não pode desativar a própria conta")

    with transaction.atomic():
        user = get_user_or_404(user_id)
        user.is_active = is_active
        user.save(update_fields=["is_active"])
        action = AuditLog.Action.ACTIVATE_USER if is_active else AuditLog.Action.DEACTIVATE_USER
        log_action(admin, action, target=user)

    logger.info("%s: id=%s por admin_id=%s", action, user_id, admin.pk)
    return public_user(user)


def delete_user(admin: User, user_id: int, force: bool) -> None:
    if user_id == admin.pk:
        raise HttpError(400, "Você não pode excluir a própria conta")

    with transaction.atomic():
        target = get_user_or_404(user_id)
        datasets = list(target.datasets.all())

        if datasets and not force:
            # Sem ?force=true, excluir fica bloqueado: apagar datasets é irreversível (o arquivo no MinIO vai
            # junto), então exige uma confirmação explícita à parte.
            raise HttpError(
                409,
                f"Este usuário possui {len(datasets)} dataset(s). Excluir também vai apagar os arquivos no MinIO, de "
                "forma irreversível. Confirme para prosseguir, ou desative a conta em vez disso.",
            )

        if datasets:
            for dataset in datasets:
                delete_dataset(dataset)
            log_action(admin, AuditLog.Action.FORCE_DELETE_USER_DATASETS, target=target, details=f"{len(datasets)} dataset(s) apagados")

        deleted_id, deleted_username = target.pk, target.username
        target.delete()  # o histórico de auditoria permanece: as referências ficam vazias (SET_NULL)
        # O usuário já não existe: id e nome vão em details.
        log_action(admin, AuditLog.Action.DELETE_USER, details=f"id={deleted_id} username={deleted_username!r}")

    logger.info("delete_user: id=%s username=%r por admin_id=%s datasets_apagados=%s", deleted_id, deleted_username, admin.pk, len(datasets))


def reset_user_password(admin: User, user_id: int, new_password: str) -> None:
    validate_new_password(new_password)
    with transaction.atomic():
        user = get_user_or_404(user_id)
        user.set_password(new_password)
        user.session_version += 1  # sessões abertas desse usuário deixam de valer
        user.save(update_fields=["password", "session_version"])
        log_action(admin, AuditLog.Action.RESET_PASSWORD, target=user)
    logger.info("reset_password: id=%s por admin_id=%s", user_id, admin.pk)


def set_user_email(admin: User, user_id: int, new_email: str | None) -> dict:
    """O administrador define ou remove o e-mail de outra conta, sem confirmação por e-mail. Fica na auditoria e a
    pessoa é avisada por uma notificação dentro do sistema. Remover o e-mail desliga o segundo passo dessa conta; por
    isso o administrador não pode mexer no PRÓPRIO e-mail por aqui (isso passa pela confirmação em "Minha conta")."""
    if user_id == admin.pk:
        raise HttpError(400, 'Para alterar o seu próprio e-mail use "Minha conta", que confirma o endereço por um código.')

    email = clean_email(new_email) if new_email and new_email.strip() else None
    with transaction.atomic():
        user = get_user_or_404(user_id)
        if email:
            ensure_email_free(email, except_user_id=user_id)
        before = mask_email(user.email) or "sem e-mail"
        user.email = email
        user.save(update_fields=["email"])
        user.email_codes.all().delete()  # códigos pendentes eram para o e-mail antigo

        after = mask_email(email) or "removido"
        log_action(admin, AuditLog.Action.ADMIN_CHANGE_EMAIL, target=user, details=f"{before} → {after}")
        message = (
            f"Um administrador alterou o seu e-mail de verificação para {after}."
            if email
            else "Um administrador removeu o seu e-mail de verificação. Sem ele, o login volta a pedir só a senha."
        )
        create_notification(user, "email_changed_by_admin", message)

    logger.info("admin_change_email: id=%s por admin_id=%s", user_id, admin.pk)
    return public_user(user)
