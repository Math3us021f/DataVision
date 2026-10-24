import os

import psycopg
from psycopg.rows import dict_row


def get_connection() -> psycopg.Connection:
    """Abre uma conexão nova com o Postgres, lendo DATABASE_URL do ambiente."""
    database_url = os.environ["DATABASE_URL"]
    return psycopg.connect(database_url, row_factory=dict_row)
