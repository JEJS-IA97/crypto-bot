"""Logging estructurado JSON fail-open (spec 005, RF-1/RF-4, D-2/D-3).

Una lI­nea JSON por evento en stdout/stderr con los campos obligatorios del
brief 27: timestamp UTC, level, service, event, mode, result + correlation_id,
asset, latency_ms y strategy_version cuando apliquen. Los valores de campos
prohibidos (claves, tokens, contraseA±as) se redactan antes de emitirse (RF-4).

Ninguna funciones de este módulo lanza excepciones hacia el llamador:
un fallo de formato o de persistencia no interrumpe el ciclo (D-3).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import settings

#: Sustituto para valores de campos prohibidos (RF-4).
REDACTED = "[REDACTED]"

#: Subcadenas (en minA?sculas) que marcan un campo prohibido (RF-4).
FORBIDDEN_KEY_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "api_secret",
    "secret",
    "token",
    "password",
    "passphrase",
    "authorization",
    "private_key",
    "credential",
    "pass",
)

#: Atributos propios de ``logging.LogRecord`` (no son extras).
_STANDARD_RECORD_ATTRS = frozenset(
    logging.makeLogRecord({}).__dict__
) | frozenset({"message", "asctime"})

#: Campos obligatorios en toda lI­nea JSON (RF-1).
BASE_FIELDS: tuple[str, ...] = (
    "timestamp",
    "level",
    "service",
    "event",
    "mode",
    "result",
    "correlation_id",
    "asset",
    "latency_ms",
    "strategy_version",
)


def _is_forbidden(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in FORBIDDEN_KEY_MARKERS)


def redact(value: Any) -> Any:
    """Devuelve ``value`` con ``[REDACTED]`` en todo campo prohibido (RF-4)."""
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if isinstance(key, str) and _is_forbidden(key)
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Formatea cada ``LogRecord`` como una lI­nea JSON (RF-1)."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            timestamp = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z")
            payload: dict[str, Any] = {
                "timestamp": timestamp,
                "level": record.levelname,
                "service": record.name,
                "event": getattr(record, "event", None),
                "mode": getattr(record, "mode", None),
                "result": getattr(record, "result", None),
                "correlation_id": getattr(record, "correlation_id", None),
                "asset": getattr(record, "asset", None),
                "latency_ms": getattr(record, "latency_ms", None),
                "strategy_version": getattr(
                    record, "strategy_version", None
                ),
                "message": record.getMessage(),
            }
            for key, value in record.__dict__.items():
                if key not in _STANDARD_RECORD_ATTRS and key not in payload:
                    payload[key] = value
            return json.dumps(
                redact(payload),
                ensure_ascii=False,
                default=str,
            )
        except Exception:  # noqa: BLE001 — D-3: jamás romper al llamador
            return json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "service": "structured_log",
                    "event": "log.format_failed",
                    "mode": None,
                    "result": "failed",
                    "message": "log record could not be formatted",
                }
            )


def configure_logging() -> logging.StreamHandler | None:
    """Instala el ``JsonFormatter`` en la raíz; idempotente (RF-1).

    Devuelve el handler que creó (``None`` si ya estaba configurado) para
    que el lifespan pueda retirarlo al apagar.
    """
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            return None
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    level = str(settings.log_level).upper()
    root.setLevel(getattr(logging, level, logging.INFO))
    return handler


def emit(
    *,
    service: str,
    event: str,
    level: str = "INFO",
    result: str = "",
    mode: str | None = None,
    asset: str | None = None,
    correlation_id: str | None = None,
    latency_ms: int | None = None,
    payload: dict[str, Any] | None = None,
    message: str = "",
    db: Any | None = None,
) -> None:
    """Emite un evento observable: persiste (si hay sesión) y loguea JSON.

    Ambos pasos son fail-open (RF-1/D-3): si la persistencia falla el
    evento se emite igual a stdout; si el log falla el llamador continA?ua.
    """
    if db is not None:
        try:
            from app.services.observability_service import record_event

            record_event(
                db,
                level=level,
                service=service,
                event=event,
                result=result or "ok",
                asset=asset,
                correlation_id=correlation_id,
                mode=mode,
                latency_ms=latency_ms,
                payload=payload,
            )
        except Exception:  # noqa: BLE001 — D-3
            pass

    try:
        logger = logging.getLogger(service)
        level_no = getattr(logging, str(level).upper(), logging.INFO)
        logger.log(
            level_no,
            message or event,
            extra={
                "event": event,
                "mode": mode,
                "result": result or "ok",
                "correlation_id": correlation_id,
                "asset": asset,
                "latency_ms": latency_ms,
                "strategy_version": settings.strategy_version,
                "payload": payload,
            },
        )
    except Exception:  # noqa: BLE001 — D-3
        pass
