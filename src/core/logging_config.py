import logging
import os

LOG_FILE_PATH = "logs/app.log"
logger = logging.getLogger("datavision")


def setup_logging() -> None:
    """Idempotente: pode ser chamada várias vezes (ex: cada TestClient novo nos testes) sem duplicar handlers."""
    if logger.handlers:
        return

    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
