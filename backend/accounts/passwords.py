"""Regras de senha nova (as mesmas do FastAPI, para a interface e as mensagens não mudarem)."""

from ninja.errors import HttpError

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # limite herdado do bcrypt; a interface mostra esta regra, então continua valendo


def validate_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HttpError(400, f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HttpError(400, f"A senha pode ter no máximo {MAX_PASSWORD_BYTES} bytes.")
