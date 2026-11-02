"""Proteções de recurso da consulta analítica: poucas consultas ao mesmo tempo e um cache pequeno do arquivo.

Cada consulta relê o arquivo do MinIO e o interpreta com o Pandas; sem limite, um usuário (ou uma tela com
muitos gráficos abrindo juntos) poderia ocupar todo o servidor. Os valores abaixo são pensados para a VM
de 2 vCPU e 4 GB: valem mais por serem finitos e conhecidos do que pelo número exato.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import pandas as pd

from src.services.profiling import load_dataframe

MAX_CONCURRENT_QUERIES = 3
QUEUE_WAIT_SECONDS = 5  # quanto uma consulta espera por uma vaga antes de desistir (503)
QUERY_TIMEOUT_SECONDS = 15  # tempo total que o cliente espera, fila incluída (504)
CACHE_MAX_FILES = 3  # arquivos de até 10 MB viram algumas dezenas de MB na memória cada um


class QueryBusyError(Exception):
    """Todas as vagas de consulta estão ocupadas e a espera acabou."""


_slots = threading.BoundedSemaphore(MAX_CONCURRENT_QUERIES)


def run_limited(task: Callable[[], Any]) -> Any:
    """Executa `task` só quando houver vaga. A vaga é devolvida quando a tarefa termina (mesmo que o
    cliente já tenha desistido por tempo esgotado), então o total em andamento nunca passa do limite."""
    if not _slots.acquire(timeout=QUEUE_WAIT_SECONDS):
        raise QueryBusyError
    try:
        return task()
    finally:
        _slots.release()


class DataFrameCache:
    """Guarda os últimos arquivos lidos. A chave é o `object_key`, que é único e nunca reutilizado
    (arquivo enviado não muda), então o cache não fica desatualizado; só é descartado para liberar memória."""

    def __init__(self, max_files: int) -> None:
        self._max_files = max_files
        self._items: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_load(self, key: str, loader: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        df = loader()  # fora do lock: não trava quem consulta outro arquivo
        with self._lock:
            self._items[key] = df
            self._items.move_to_end(key)
            while len(self._items) > self._max_files:
                self._items.popitem(last=False)
        return df

    def evict(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def __len__(self) -> int:
        return len(self._items)


dataframe_cache = DataFrameCache(CACHE_MAX_FILES)


def load_dataframe_cached(object_key: str, extension: str) -> pd.DataFrame:
    # O motor não altera o DataFrame recebido (trabalha em cópias), então ele pode ser compartilhado.
    return dataframe_cache.get_or_load(object_key, lambda: load_dataframe(object_key, extension))
