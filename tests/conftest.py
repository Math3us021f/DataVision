import pytest

from src.rate_limit import _failed_attempts


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Evita que o estado do rate limiter (em memória, global no processo) vaze entre testes."""
    _failed_attempts.clear()
    yield
    _failed_attempts.clear()
