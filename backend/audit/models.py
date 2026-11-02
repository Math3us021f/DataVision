from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Histórico das ações administrativas. Ao excluir um usuário, o registro permanece: as referências
    ficam vazias (SET_NULL) e o nome vai em `details`."""

    class Action(models.TextChoices):
        CREATE_USER = "create_user", "Criação de usuário"
        ACTIVATE_USER = "activate_user", "Ativação de usuário"
        DEACTIVATE_USER = "deactivate_user", "Desativação de usuário"
        DELETE_USER = "delete_user", "Exclusão de usuário"
        FORCE_DELETE_USER_DATASETS = "force_delete_user_datasets", "Exclusão forçada de datasets"
        RESET_PASSWORD = "reset_password", "Redefinição de senha (admin)"
        CHANGE_OWN_PASSWORD = "change_own_password", "Troca da própria senha"
        REVOKE_OTHER_SESSIONS = "revoke_other_sessions", "Encerramento de outras sessões"
        CHANGE_OWN_EMAIL = "change_own_email", "Troca do próprio e-mail"
        ADMIN_CHANGE_EMAIL = "admin_change_email", "E-mail alterado por administrador"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_actions")
    action = models.CharField(max_length=50, choices=Action.choices)
    target = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_targets")
    details = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]  # os mais recentes primeiro, como na tela de auditoria
