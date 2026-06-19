# infrastructure/ratelimit.py
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Tuple

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def register_failure(key: str, *, window_seconds: int) -> None:
    """Registra uma falha de autenticação para a chave dada."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        bucket.append(now)


def is_limited(key: str, *, max_attempts: int, window_seconds: int) -> Tuple[bool, int]:
    """
    Retorna (limited, retry_after_seconds).
    limited=True se o número de falhas na janela >= max_attempts.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_attempts:
            oldest = bucket[0]
            retry = int(oldest + window_seconds - now) + 1
            return True, max(retry, 1)
        return False, 0


def reset(key: str) -> None:
    """Limpa o histórico de falhas após login bem-sucedido."""
    with _lock:
        _buckets.pop(key, None)
