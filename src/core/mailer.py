"""Envio de e-mail por SMTP. Tudo vem de variáveis de ambiente; nada de segredo no código.

Em desenvolvimento o Compose aponta para o Mailpit (um coletor local: os e-mails ficam numa tela em
http://localhost:8025 e nada sai da máquina). Para usar um provedor de verdade, defina no `.env`:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_SECURITY=starttls
    SMTP_USER=...        SMTP_PASSWORD=...        SMTP_FROM=...

`SMTP_SECURITY` é opcional: `starttls` (padrão na porta 587), `ssl` (padrão na 465) ou `none` (demais portas,
só para o coletor local). No Compose de desenvolvimento essas variáveis se chamam `DEV_SMTP_*` (ver compose.yaml);
`SMTP_*` valem no servidor (compose.prod.yaml).
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

from src.core.logging_config import logger

SMTP_TIMEOUT_SECONDS = 10


class MailNotConfiguredError(Exception):
    """Faltam as variáveis SMTP: o sistema não tem como enviar e-mail."""


class MailSendError(Exception):
    """O servidor de e-mail recusou ou não respondeu."""


def send_email(to_address: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    if not host or not sender:
        raise MailNotConfiguredError

    port = int(os.environ.get("SMTP_PORT", "587"))
    # Sem SMTP_SECURITY, a porta decide: 465 = SSL direto, 587 = STARTTLS, qualquer outra (ex.: 1025 do
    # Mailpit) = sem criptografia. Provedores reais exigem TLS, então o padrão para eles já é o seguro.
    security = (os.environ.get("SMTP_SECURITY") or {465: "ssl", 587: "starttls"}.get(port, "none")).lower()
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    try:
        context = ssl.create_default_context()
        if security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if security == "starttls":
                server.starttls(context=context)
            if user:
                server.login(user, password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Só o tipo do erro vai para o log: a mensagem pode trazer o endereço ou detalhes do servidor.
        logger.error("Falha ao enviar e-mail (%s)", type(exc).__name__)
        raise MailSendError from exc
