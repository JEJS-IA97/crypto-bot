"""Esquema estricto del analista IA (spec 007, RF-2).

Contrato de la §6 del brief: I/O estructurado, ``extra="forbid"``,
rangos 0..1 y `direction` sin cortos (D-13: spot solo LONG/NEUTRAL).
Cualquier desviación levanta ``SchemaViolation``; nunca se parsea prosa.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SchemaViolation(ValueError):
    """La respuesta del modelo no cumple el esquema (RF-2)."""


class AdvisorResponse(BaseModel):
    """I/O estructurado exigido al modelo (brief §6)."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["BUY", "SELL", "WAIT"]
    direction: Literal["LONG", "NEUTRAL"]
    confidence: Decimal = Field(ge=0, le=1)
    setup_quality: Decimal = Field(ge=0, le=1)
    risk_flags: list[str]
    supporting_factors: list[str]
    contradicting_factors: list[str]
    invalidating_conditions: list[str]
    time_horizon: str
    suggested_entry_zone: str | None = None
    suggested_stop_zone: str | None = None
    suggested_take_profit_zone: str | None = None
    reason_codes: list[str]
    required_next_check: str
    data_quality: dict[str, str]

    @classmethod
    def from_json(cls, text: str) -> "AdvisorResponse":
        """Parsea la respuesta cruda; prosa o esquema inválido ⇒ violación."""
        try:
            payload = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise SchemaViolation(f"answer is not JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise SchemaViolation("answer must be a JSON object")
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:
            raise SchemaViolation(
                f"invalid advisor response: {exc}"
            ) from exc
