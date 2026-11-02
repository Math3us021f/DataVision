import time
from collections import defaultdict

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60.0

# Chave = (ip, username). Em memória: some num restart e não é compartilhado
# entre processos/réplicas — suficiente para o MVP com um único processo da app,
# mas é uma limitação conhecida se a aplicação escalar para múltiplas réplicas
# (nesse caso, precisaria de um armazenamento compartilhado, ex: Redis).
_failed_attempts: dict[tuple[str, str], list[float]] = defaultdict(list)


def _prune_old(key: tuple[str, str]) -> None:
    cutoff = time.monotonic() - LOCKOUT_SECONDS
    _failed_attempts[key] = [t for t in _failed_attempts[key] if t > cutoff]


def is_locked_out(key: tuple[str, str]) -> bool:
    _prune_old(key)
    return len(_failed_attempts[key]) >= MAX_ATTEMPTS


def register_failed_attempt(key: tuple[str, str]) -> None:
    _failed_attempts[key].append(time.monotonic())


def reset_attempts(key: tuple[str, str]) -> None:
    _failed_attempts.pop(key, None)
