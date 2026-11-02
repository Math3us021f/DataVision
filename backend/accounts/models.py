from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils.crypto import salted_hmac


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
    # Sobe quando a senha é trocada ou a pessoa encerra as outras sessões: cookies com a versão antiga deixam de valer.
    session_version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

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

    def get_session_auth_hash(self) -> str:
        """Por padrão o Django derruba as sessões quando a SENHA muda (comparando um hash dela guardado na sessão).
        Aqui quem manda é a `session_version` (a política de sessão a confere e dá a mensagem certa: "Sessão
        encerrada"), então este hash é fixo e não deixa o Django derrubar a sessão por conta própria."""
        return salted_hmac("accounts.User.session_hash", "v1", secret=settings.SECRET_KEY, algorithm="sha256").hexdigest()


class LoginEvent(models.Model):
    """Acessos recentes de cada usuário (a tela "Atividade"). De propósito NÃO guarda IP nem o texto do
    navegador: só a data, o resultado e um resumo ("Chrome · Windows")."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_events")
    success = models.BooleanField()
    browser = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-id"], name="login_events_user_idx")]


class EmailCode(models.Model):
    """Código de verificação pendente (login em dois passos ou troca de e-mail). Guarda só o HMAC do código."""

    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        EMAIL_CHANGE = "email_change", "Troca de e-mail"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_codes")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    new_email = models.EmailField(max_length=254, null=True, blank=True)  # só na troca de e-mail
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(auto_now_add=True)
    window_started_at = models.DateTimeField(auto_now_add=True)
    sends_in_window = models.PositiveIntegerField(default=1)

    class Meta:
        # Um código pendente por usuário e finalidade: pedir outro substitui o anterior.
        constraints = [models.UniqueConstraint(fields=["user", "purpose"], name="email_codes_user_purpose_unique")]


class Notification(models.Model):
    """Aviso dentro do sistema, para a própria pessoa (ex.: "um administrador alterou o seu e-mail")."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=50)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-id"], name="notifications_user_idx")]
