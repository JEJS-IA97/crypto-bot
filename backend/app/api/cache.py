"""Caché de respuestas para el panel: la base (Neon) tarda 1-3 s por consulta desde la PC.

`swr(ttl)`: si la respuesta tiene menos de `ttl` s, se devuelve tal cual; si es más vieja, se
devuelve la vieja al instante y se recalcula en segundo plano con una sesión propia. Solo la
primera petición de cada endpoint espera a la base.
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable

from app import database
from app.config import settings

# Solo con la base remota: en local/tests (SQLite) responde directo, sin caché.
ENABLED = not settings.database_url.startswith("sqlite")

_store: dict[tuple, tuple[float, Any]] = {}
_busy: set[tuple] = set()
_lock = threading.Lock()


def swr(ttl: float) -> Callable:
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__name__, tuple(sorted((k, repr(v)) for k, v in kwargs.items() if k != "db")))

            def compute(fresh_session: bool):
                if fresh_session and "db" in kwargs:
                    with database.SessionLocal() as db:
                        value = fn(*args, **{**kwargs, "db": db})
                else:
                    value = fn(*args, **kwargs)
                with _lock:
                    _store[key] = (time.time(), value)
                return value

            if not ENABLED:
                return fn(*args, **kwargs)
            hit = _store.get(key)
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
            if hit:
                with _lock:
                    start = key not in _busy
                    _busy.add(key)
                if start:
                    def refresh():
                        try:
                            compute(True)
                        finally:
                            with _lock:
                                _busy.discard(key)
                    threading.Thread(target=refresh, daemon=True).start()
                return hit[1]
            return compute(False)

        return wrapper

    return deco


def clear() -> None:
    with _lock:
        _store.clear()
