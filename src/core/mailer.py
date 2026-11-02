"""Envio de e-mail por SMTP. Tudo vem de variáveis de ambiente; nada de segredo no código.

Provedor de verdade (Gmail, por exemplo), em `.env` no desenvolvimento ou em `.env.prod` no servidor:

    SMTP_HOST=smtp.gmail.com   SMTP_PORT=587   SMTP_USER=...   SMTP_PASSWORD=...   SMTP_FROM=...

`SMTP_SECURITY` é opcional: `starttls` (padrão na porta 587), `ssl` (padrão na 465) ou `none` (demais portas,
só para o coletor local). Sem `SMTP_HOST`, o Compose de desenvolvimento usa o Mailpit (coletor local: os
e-mails aparecem em http://localhost:8025 e nada sai da máquina).

Coletor de segurança (`MAIL_SINK_HOST`, definido só no Compose de desenvolvimento): e-mails para endereços de
MENTIRA (domínios reservados como exemplo.com e example.com, e os finais .test, .invalid, .localhost, .example)
nunca vão para o provedor real: vão para o coletor. Assim os testes automáticos, que cadastram endereços de
mentira, não disparam e-mails de verdade pela sua conta, e endereços reais continuam sendo entregues.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

from src.core.logging_config import logger

SMTP_TIMEOUT_SECONDS = 10
FAKE_DOMAINS = {"exemplo.com", "example.com", "example.net", "example.org"}
FAKE_TLDS = {"test", "invalid", "localhost", "example"}


class MailNotConfiguredError(Exception):
    """Faltam as variáveis SMTP: o sistema não tem como enviar e-mail."""


class MailSendError(Exception):
    """O servidor de e-mail recusou ou não respondeu."""


def is_fake_address(address: str) -> bool:
    domain = address.rpartition("@")[2].strip().lower()
    return domain in FAKE_DOMAINS or domain.rpartition(".")[2] in FAKE_TLDS


def _settings_for(to_address: str) -> dict:
    sender = os.environ.get("SMTP_FROM", "").strip() or "datavision@localhost"

    sink_host = os.environ.get("MAIL_SINK_HOST", "").strip()
    if sink_host and is_fake_address(to_address):
        return {"host": sink_host, "port": int(os.environ.get("MAIL_SINK_PORT", "1025")), "security": "none",
                "user": "", "password": "", "sender": sender}

    host = os.environ.get("SMTP_HOST", "").strip()
    if not host or not os.environ.get("SMTP_FROM", "").strip():
        raise MailNotConfiguredError
    port = int(os.environ.get("SMTP_PORT", "587"))
    # Sem SMTP_SECURITY, a porta decide: 465 = SSL direto, 587 = STARTTLS, qualquer outra (ex.: 1025 do
    # Mailpit) = sem criptografia. Provedores reais exigem TLS, então o padrão para eles já é o seguro.
    security = (os.environ.get("SMTP_SECURITY") or {465: "ssl", 587: "starttls"}.get(port, "none")).lower()
    return {"host": host, "port": port, "security": security, "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""), "sender": sender}


def send_email(to_address: str, subject: str, body: str) -> None:
    cfg = _settings_for(to_address)

    message = EmailMessage()
    message["From"] = cfg["sender"]
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    try:
        context = ssl.create_default_context()
        if cfg["security"] == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=SMTP_TIMEOUT_SECONDS, context=context)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if cfg["security"] == "starttls":
                server.starttls(context=context)
            if cfg["user"]:
                server.login(cfg["user"], cfg["password"])
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Só o tipo do erro (e o código do SMTP, se houver) vai para o log: a mensagem pode trazer o endereço.
        code = getattr(exc, "smtp_code", None)
        logger.error("Falha ao enviar e-mail (%s%s)", type(exc).__name__, f", código {code}" if code else "")
        raise MailSendError from exc
