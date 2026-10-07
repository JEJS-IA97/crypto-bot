"""Tests rojos — Spec 007: esquema estricto del analista (RF-2).

``AdvisorResponse`` acepta JSON válido según el contrato de la §6 del brief
(``extra="forbid"``, rangos 0..1, `direction` sin cortos) y cualquier
desviación levanta ``SchemaViolation``.
"""

import json
import unittest
from decimal import Decimal

VALID = {
    "decision": "WAIT",
    "direction": "LONG",
    "confidence": 0.64,
    "setup_quality": 0.71,
    "risk_flags": ["near_range_high"],
    "supporting_factors": ["ema_trend_up", "volume_above_avg"],
    "contradicting_factors": ["near_resistance"],
    "invalidating_conditions": ["close_below_range_low"],
    "time_horizon": "4h",
    "suggested_entry_zone": None,
    "suggested_stop_zone": None,
    "suggested_take_profit_zone": None,
    "reason_codes": ["trend_aligned"],
    "required_next_check": "volume_on_breakout",
    "data_quality": {"order_book": "fresh", "news": "disabled"},
}


class SchemaTests(unittest.TestCase):
    def test_valid_payload_parses(self) -> None:
        from app.domain.ai_schema import AdvisorResponse

        parsed = AdvisorResponse.from_json(json.dumps(VALID))

        self.assertEqual(parsed.decision, "WAIT")
        self.assertEqual(parsed.direction, "LONG")
        self.assertIsInstance(parsed.confidence, Decimal)
        self.assertIsInstance(parsed.setup_quality, Decimal)
        self.assertEqual(
            parsed.confidence.quantize(Decimal("0.0001")), Decimal("0.6400")
        )
        self.assertEqual(
            parsed.supporting_factors[0], "ema_trend_up"
        )
        self.assertEqual(
            parsed.invalidating_conditions[0], "close_below_range_low"
        )
        self.assertIsNone(parsed.suggested_entry_zone)
        self.assertEqual(parsed.data_quality["news"], "disabled")

    def test_extra_field_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        payload = dict(VALID, hallucination="never")
        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json(json.dumps(payload))

    def test_confidence_above_one_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        payload = dict(VALID, confidence=1.5)
        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json(json.dumps(payload))

    def test_negative_setup_quality_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        payload = dict(VALID, setup_quality=-0.1)
        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json(json.dumps(payload))

    def test_short_direction_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        payload = dict(VALID, direction="SHORT")
        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json(json.dumps(payload))

    def test_unknown_decision_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        payload = dict(VALID, decision="HOLD")
        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json(json.dumps(payload))

    def test_missing_required_field_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        payload = dict(VALID)
        del payload["risk_flags"]
        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json(json.dumps(payload))

    def test_prose_answer_is_rejected(self) -> None:
        from app.domain.ai_schema import AdvisorResponse, SchemaViolation

        with self.assertRaises(SchemaViolation):
            AdvisorResponse.from_json("Comprar BTC porque parece alcista.")


if __name__ == "__main__":
    unittest.main()
