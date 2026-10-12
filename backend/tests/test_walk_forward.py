"""Walk-forward ORB: validación de velas y construcción de folds (spec 011)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.services.walk_forward_service import (
    WalkForwardConfig,
    build_folds,
    candles_in_range,
    iter_grid,
    select_params,
    split_train_validation,
    validate_candles,
)
from fixtures_klines import (
    breakout_day,
    orb_candle,
    ranging_win_day,
    trend_hourly_flat,
    walk_forward_dataset,
)

_START = date(2026, 1, 1)


def _hourly() -> list:
    """Velas 1h que dejan pasar el filtro ORB en enero (spec 012)."""
    return trend_hourly_flat(count=24 * 20, end=datetime(2026, 1, 12, 0))


def _config(**overrides: object) -> WalkForwardConfig:
    defaults: dict[str, object] = {
        "symbols": ("BTCUSDT",),
        "train_days": 10,
        "test_days": 5,
        "step_days": 5,
        "capital_usd": Decimal("20"),
    }
    defaults.update(overrides)
    return WalkForwardConfig(**defaults)  # type: ignore[arg-type]


class ValidateCandlesTest(unittest.TestCase):
    """RF-1 / D-8: validación mínima de velas."""

    def test_accepts_ordered_ohlc(self) -> None:
        candles = walk_forward_dataset(3, _START)
        validate_candles(candles)  # no lanza

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_candles([])

    def test_rejects_duplicate_timestamp(self) -> None:
        day = _START
        first = orb_candle(day, 9, 0, "99", "99.5", "98.5", "99")
        duplicate = orb_candle(day, 9, 0, "99", "99.6", "98.4", "99.2")
        with self.assertRaises(ValueError):
            validate_candles([first, duplicate])

    def test_rejects_out_of_order(self) -> None:
        later = orb_candle(_START, 9, 5, "99", "99.5", "98.5", "99")
        earlier = orb_candle(_START, 9, 0, "99", "99.5", "98.5", "99")
        with self.assertRaises(ValueError):
            validate_candles([later, earlier])

    def test_rejects_low_above_open(self) -> None:
        bad = orb_candle(_START, 9, 0, "99", "100", "99.5", "99.8")
        with self.assertRaises(ValueError):
            validate_candles([bad])

    def test_rejects_high_below_close(self) -> None:
        bad = orb_candle(_START, 9, 0, "99", "98.5", "98", "99")
        with self.assertRaises(ValueError):
            validate_candles([bad])


class BuildFoldsTest(unittest.TestCase):
    """RF-2 / D-3: construcción exacta de folds rodantes."""

    def test_exact_fold_boundaries(self) -> None:
        candles = walk_forward_dataset(40, _START)
        folds = build_folds({"BTCUSDT": candles}, _config())

        self.assertEqual(len(folds), 6)
        first = folds[0]
        self.assertEqual(first.train_start, date(2026, 1, 1))
        self.assertEqual(first.train_end, date(2026, 1, 11))
        self.assertEqual(first.test_start, date(2026, 1, 11))
        self.assertEqual(first.test_end, date(2026, 1, 16))
        last = folds[-1]
        self.assertEqual(last.train_start, date(2026, 1, 26))
        self.assertEqual(last.test_end, date(2026, 2, 10))
        # El test de un fold nunca toca el train de ningún fold.
        for fold in folds:
            self.assertGreaterEqual(fold.test_start, fold.train_end)
            self.assertEqual((fold.train_end - fold.train_start).days, 10)
            self.assertEqual((fold.test_end - fold.test_start).days, 5)

    def test_step_slides_train_start(self) -> None:
        candles = walk_forward_dataset(40, _START)
        folds = build_folds({"BTCUSDT": candles}, _config())
        self.assertEqual(
            folds[1].train_start, date(2026, 1, 6)
        )  # paso de 5 días

    def test_single_fold_minimum_dataset(self) -> None:
        candles = walk_forward_dataset(15, _START)
        folds = build_folds({"BTCUSDT": candles}, _config())
        self.assertEqual(len(folds), 1)

    def test_dataset_too_short_raises(self) -> None:
        candles = walk_forward_dataset(14, _START)
        with self.assertRaises(ValueError):
            build_folds({"BTCUSDT": candles}, _config())

    def test_empty_symbol_raises(self) -> None:
        candles = walk_forward_dataset(40, _START)
        with self.assertRaises(ValueError):
            build_folds({"BTCUSDT": [], "ETHUSDT": candles}, _config())

    def test_empty_mapping_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_folds({}, _config())

    def test_deterministic(self) -> None:
        candles = walk_forward_dataset(40, _START)
        self.assertEqual(
            build_folds({"BTCUSDT": candles}, _config()),
            build_folds({"BTCUSDT": candles}, _config()),
        )


class CandlesInRangeTest(unittest.TestCase):
    """RF-2: recorte de velas por rango de fechas [start, end)."""

    def test_end_is_exclusive(self) -> None:
        candles = walk_forward_dataset(10, _START)
        sliced = candles_in_range(candles, _START, date(2026, 1, 3))
        self.assertTrue(all(c.open_time.date() < date(2026, 1, 3) for c in sliced))
        self.assertTrue(any(c.open_time.date() == date(2026, 1, 2) for c in sliced))

    def test_deterministic(self) -> None:
        candles = walk_forward_dataset(10, _START)
        self.assertEqual(
            candles_in_range(candles, _START, date(2026, 1, 4)),
            candles_in_range(candles, _START, date(2026, 1, 4)),
        )


class SplitTrainValidationTest(unittest.TestCase):
    """Constitución #9: validación interna = última fracción del train."""

    def test_validation_is_tail_slice(self) -> None:
        candles = walk_forward_dataset(10, _START)
        train_part, validation = split_train_validation(candles, 0.15)
        self.assertEqual(len(candles), 80)  # 8 velas/día (sesión ORB)
        self.assertEqual(len(validation), 12)  # max(1, int(80*0.15))
        self.assertEqual(len(train_part), 68)
        self.assertEqual(train_part + validation, candles)

    def test_too_short_train_raises(self) -> None:
        only = [orb_candle(_START, 9, 0, "99", "99.5", "98.5", "99")]
        with self.assertRaises(ValueError):
            split_train_validation(only, 0.15)

    def test_rejects_bad_ratio(self) -> None:
        candles = walk_forward_dataset(5, _START)
        with self.assertRaises(ValueError):
            split_train_validation(candles, 0.0)


class IterGridTest(unittest.TestCase):
    """RF-2 / const. #3: candidatos del grid filtrados por pérdida ≤ 1 USD."""

    def test_default_grid_is_3x3(self) -> None:
        grid = iter_grid(_config())
        self.assertEqual(len(grid), 9)

    def test_filters_candidates_above_one_usd(self) -> None:
        grid = iter_grid(
            _config(
                stop_loss_grid=(Decimal("1.0"), Decimal("6.0")),
                take_profit_grid=(Decimal("2.0"),),
            )
        )
        # SL 6 % a 20 USD ⇒ 1.20 USD de pérdida ⇒ descartado (const. #3).
        self.assertEqual(len(grid), 1)
        self.assertEqual(grid[0].stop_loss_pct, Decimal("1.0"))

    def test_all_candidates_carry_config_costs(self) -> None:
        config = _config(
            fee_rate=Decimal("0.002"),
            slippage_pct=Decimal("0.07"),
        )
        for candidate in iter_grid(config):
            self.assertEqual(candidate.fee_rate, Decimal("0.002"))
            self.assertEqual(candidate.slippage_pct, Decimal("0.07"))
            self.assertEqual(candidate.capital_usd, Decimal("20"))


class SelectParamsTest(unittest.TestCase):
    """RF-2: selección por validación, empate conservador, sin look-ahead."""

    def _zero_cost_config(self) -> WalkForwardConfig:
        return _config(
            fee_rate=Decimal("0"),
            slippage_pct=Decimal("0"),
        )

    def test_picks_tp_one_on_ranging_days(self) -> None:
        candles: list = []
        for offset in range(10):
            candles += ranging_win_day(_START + timedelta(days=offset))
        config = self._zero_cost_config()
        train_part, validation = split_train_validation(candles, 0.15)
        best = select_params(train_part, validation, config, hourly=_hourly())
        # TP=1 gana en validación; SL irrelevante ⇒ empate ⇒ menor SL.
        self.assertEqual(best, (Decimal("1.0"), Decimal("1.0")))

    def test_pump_in_test_does_not_change_selection(self) -> None:
        # look-ahead: un pico dentro del test no puede alterar la selección
        # del train (RF-2 / D-3).
        config = self._zero_cost_config()
        base: list = []
        for offset in range(15):
            base += ranging_win_day(_START + timedelta(days=offset))
        pumped = [
            candle
            for offset in range(15)
            for candle in (
                breakout_day(_START + timedelta(days=offset), pump=True)
                if offset == 12  # dentro del test del fold 0 [10, 15)
                else ranging_win_day(_START + timedelta(days=offset))
            )
        ]

        fold_base = build_folds({"BTCUSDT": base}, config)[0]
        fold_pump = build_folds({"BTCUSDT": pumped}, config)[0]
        self.assertEqual(fold_base, fold_pump)

        train_base = candles_in_range(
            base, fold_base.train_start, fold_base.train_end
        )
        train_pump = candles_in_range(
            pumped, fold_pump.train_start, fold_pump.train_end
        )
        split_base = split_train_validation(train_base, config.validation_ratio)
        split_pump = split_train_validation(train_pump, config.validation_ratio)
        self.assertEqual(
            select_params(*split_base, config, hourly=_hourly()),
            select_params(*split_pump, config, hourly=_hourly()),
        )

    def test_missing_score_candles_raises(self) -> None:
        with self.assertRaises(ValueError):
            select_params([], [], self._zero_cost_config())


if __name__ == "__main__":
    unittest.main()
