import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE_PATH = "logs/app.log"
# O log gira sozinho: ao passar de 5 MB vira app.log.1 (e assim por diante), guardando 5 arquivos antigos.
# Sem isso, o arquivo cresceria sem limite e a tela de logs ficaria cada vez mais lenta.
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5
logger = logging.getLogger("datavision")


def build_file_handler(path: str, max_bytes: int = LOG_MAX_BYTES, backup_count: int = LOG_BACKUP_COUNT) -> RotatingFileHandler:
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    return handler


def setup_logging() -> None:
    """Idempotente: pode ser chamada várias vezes (ex: cada TestClient novo nos testes) sem duplicar handlers."""
    if logger.handlers:
        return

    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.addHandler(build_file_handler(LOG_FILE_PATH))


def read_log_tail(path: str, limit: int, block_size: int = 8192) -> list[str]:
    """Últimas `limit` linhas do arquivo, lendo de trás para frente só o necessário (não o arquivo inteiro)."""
    try:
        with open(path, "rb") as log_file:
            position = log_file.seek(0, os.SEEK_END)
            data = b""
            # limit + 1 quebras de linha garantem `limit` linhas completas (a primeira peça pode vir cortada).
            while position > 0 and data.count(b"\n") <= limit:
                step = min(block_size, position)
                position -= step
                log_file.seek(position)
                data = log_file.read(step) + data
    except FileNotFoundError:
        return []

    # Decodifica só depois de juntar os blocos: um caractere de vários bytes pode ter sido cortado entre dois deles.
    return data.decode("utf-8", errors="replace").splitlines()[-limit:]
