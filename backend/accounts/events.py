"""Acessos recentes de cada usuário (a tela "Atividade" de Minha conta)."""

from accounts.models import LoginEvent

MAX_LOGIN_EVENTS = 50  # retenção por usuário: os mais antigos são apagados

_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (
    ("Windows", "Windows"),
    ("Android", "Android"),
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)


def summarize_user_agent(user_agent: str | None) -> str:
    """"Chrome · Windows". Só este resumo é guardado: nem o texto original do navegador nem o IP."""
    if not user_agent:
        return "Desconhecido"
    browser = next((name for marker, name in _BROWSERS if marker in user_agent), "Outro navegador")
    system = next((name for marker, name in _SYSTEMS if marker in user_agent), "sistema desconhecido")
    return f"{browser} · {system}"


def record_login_event(user, success: bool, user_agent: str | None) -> None:
    LoginEvent.objects.create(user=user, success=success, browser=summarize_user_agent(user_agent))
    keep = list(LoginEvent.objects.filter(user=user).order_by("-id").values_list("id", flat=True)[:MAX_LOGIN_EVENTS])
    LoginEvent.objects.filter(user=user).exclude(id__in=keep).delete()
