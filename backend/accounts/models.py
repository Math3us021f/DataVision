from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username: str, password: str | None = None, **extra):
        user = self.model(username=username.strip(), **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, password: str | None = None, **extra):
        # No DataVision "superusuário" é o administrador: a mesma coisa que is_admin.
        return self.create_user(username, password, is_admin=True, **extra)


class User(AbstractBaseUser):
    """Usuário do DataVision. O modelo próprio (em vez do padrão do Django) vem desde o começo porque trocá-lo
    depois, com dados no banco, é muito difícil. Campos extras ficam aqui: e-mail de verificação, nome de
    exibição e preferências."""

    username = models.CharField("usuário", max_length=150, unique=True)
    email = models.EmailField("e-mail de verificação", max_length=254, null=True, blank=True)
    display_name = models.CharField("nome de exibição", max_length=60, null=True, blank=True)
    preferences = models.JSONField("preferências", default=dict, blank=True)
    is_admin = models.BooleanField("administrador", default=False)
    is_active = models.BooleanField("ativo", default=True)
    date_joined = models.DateTimeField("criado em", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        constraints = [
            # E-mail único sem diferenciar maiúsculas (vários usuários sem e-mail são permitidos: NULL).
            models.UniqueConstraint(Lower("email"), name="users_email_unique", condition=models.Q(email__isnull=False)),
        ]

    def __str__(self) -> str:
        return self.username

    # O painel admin do Django (opcional, de emergência) só deixa entrar quem é administrador do DataVision.
    @property
    def is_staff(self) -> bool:
        return self.is_admin

    @property
    def is_superuser(self) -> bool:
        return self.is_admin

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_active and self.is_admin

    def has_module_perms(self, app_label) -> bool:
        return self.is_active and self.is_admin
