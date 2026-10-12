"""Métricas walk-forward: costes, Sharpe, drawdown, PF, expectancy (spec 011)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.services.strategy_lab_service import (
    KlineTrade,
    OrbBacktestConfig,
    backtest_orb,
)
from app.services.walk_forward_service import (
    WalkForwardConfig,
    aggregate_metrics,
    compute_fold_metrics,
    daily_equity_series,
    daily_returns,
    daily_sharpe,
    max_drawdown,
)
from fixtures_klines import trend_hourly_flat, walk_forward_dataset

_CAPITAL = Decimal("20")
_DAY0 = date(2026, 3, 1)


def _dt(day_offset: int, hour: int = 14) -> datetime:
    return datetime.combine(
        _DAY0 + timedelta(days=day_offset),
        datetime.min.time(),
    ).replace(hour=hour)


def _trade(pnl: str, fees: str, exit_day: int) -> KlineTrade:
    return KlineTrade(
        entry_time=_dt(exit_day - 1),
        exit_time=_dt(exit_day),
        entry_price=Decimal("100"),
        exit_price=Decimal("101"),
        quantity=Decimal("0.2"),
        fees_usd=Decimal(fees),
        pnl_usd=Decimal(pnl),
    )


class DailySharpeTest(unittest.TestCase):
    """RF-4 / D-5: Sharpe poblacional anualizado ×√252."""

    def test_less_than_two_days_is_zero(self) -> None:
        self.assertEqual(daily_sharpe([_CAPITAL]), Decimal("0"))

    def test_flat_equity_is_zero(self) -> None:
        series = [_CAPITAL, _CAPITAL, _CAPITAL]
        returns = daily_returns(series, _CAPITAL)
        self.assertEqual(daily_sharpe(returns), Decimal("0"))

    def test_hand_checked_two_returns(self) -> None:
        # retornos 0.2 y 0.4 ⇒ media 0.3, desv poblacional 0.1 ⇒ 3×√252
        series = [Decimal("24"), Decimal("33.6")]
        returns = daily_returns(series, _CAPITAL)
        self.assertEqual(daily_sharpe(returns), Decimal("47.6235"))


class MaxDrawdownTest(unittest.TestCase):
    """RF-4: drawdown máximo en USD y % del pico."""

    def test_hand_checked(self) -> None:
        curve = [
            Decimal("20"),
            Decimal("22"),
            Decimal("19.8"),
            Decimal("21"),
        ]
        usd, pct = max_drawdown(curve)
        self.assertEqual(usd, Decimal("2.2"))
        self.assertEqual(pct, Decimal("10"))

    def test_monotonic_up_is_zero(self) -> None:
        usd, pct = max_drawdown([Decimal("20"), Decimal("21")])
        self.assertEqual(usd, Decimal("0"))
        self.assertEqual(pct, Decimal("0"))


class ComputeFoldMetricsTest(unittest.TestCase):
    """RF-3/RF-4: métricas por ventana contra valores calculados a mano."""

    def test_single_win_hand_checked(self) -> None:
        trades = [_trade("2", "0.1", exit_day=1)]
        metrics = compute_fold_metrics(
            trades,  # type: ignore[arg-type]
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=2),
        )
        self.assertEqual(metrics.trades, 1)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.net_pnl_usd, Decimal("2"))
        self.assertEqual(metrics.fees_usd, Decimal("0.1"))
        self.assertEqual(metrics.return_pct, Decimal("10"))
        self.assertEqual(metrics.expectancy_usd, Decimal("2"))
        self.assertIsNone(metrics.profit_factor)  # sin pérdidas ⇒ n/a
        self.assertEqual(metrics.max_drawdown_usd, Decimal("0"))
        # equity diaria [20, 22] ⇒ retornos [0, 0.1] ⇒ Sharpe 1×√252
        self.assertEqual(metrics.sharpe, Decimal("15.8745"))

    def test_win_and_loss_profit_factor(self) -> None:
        trades = [
            _trade("2", "0.1", exit_day=1),
            _trade("-1", "0.1", exit_day=2),
        ]
        metrics = compute_fold_metrics(
            trades,  # type: ignore[arg-type]
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=3),
        )
        self.assertEqual(metrics.net_pnl_usd, Decimal("1"))
        self.assertEqual(metrics.profit_factor, Decimal("2"))
        self.assertEqual(metrics.expectancy_usd, Decimal("0.5"))
        self.assertEqual(metrics.return_pct, Decimal("5"))

    def test_no_trades_is_all_zeros(self) -> None:
        metrics = compute_fold_metrics(
            [],
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=3),
        )
        self.assertEqual(metrics.trades, 0)
        self.assertEqual(metrics.net_pnl_usd, Decimal("0"))
        self.assertEqual(metrics.sharpe, Decimal("0"))
        self.assertIsNone(metrics.profit_factor)
        self.assertEqual(metrics.expectancy_usd, Decimal("0"))

    def test_daily_equity_carries_flat_days(self) -> None:
        trades = [_trade("2", "0", exit_day=1)]
        series = daily_equity_series(
            trades,  # type: ignore[arg-type]
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=4),
        )
        self.assertEqual(
            series,
            [Decimal("20"), Decimal("22"), Decimal("22"), Decimal("22")],
        )


class AggregateMetricsTest(unittest.TestCase):
    """RF-4/D-7: agregado = suma aritmética + Sharpe sobre retornos unidos."""

    def test_pooled_and_summed(self) -> None:
        fold_a = compute_fold_metrics(
            [_trade("2", "0.1", exit_day=1)],  # type: ignore[list-item]
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=2),
        )
        fold_b = compute_fold_metrics(
            [_trade("-1", "0.1", exit_day=1)],  # type: ignore[list-item]
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=2),
        )
        returns_a = daily_returns([Decimal("20"), Decimal("22")], _CAPITAL)
        returns_b = daily_returns([Decimal("20"), Decimal("19")], _CAPITAL)
        total = aggregate_metrics(
            [fold_a, fold_b],
            [returns_a, returns_b],
            _CAPITAL,
        )
        self.assertEqual(total.net_pnl_usd, Decimal("1"))
        self.assertEqual(total.trades, 2)
        self.assertEqual(total.winning_trades, 1)
        self.assertEqual(total.fees_usd, Decimal("0.2"))
        self.assertEqual(total.profit_factor, Decimal("2"))  # 2 / 1
        self.assertEqual(total.expectancy_usd, Decimal("0.5"))
        # base: capital × nº de ventanas (20 × 2)
        self.assertEqual(total.return_pct, Decimal("2.5"))
        # drawdown del agregado = máximo entre ventanas (1 de la B: 20→19)
        self.assertEqual(total.max_drawdown_usd, Decimal("1"))
        self.assertEqual(total.max_drawdown_pct, Decimal("5"))


class EngineTradeListTest(unittest.TestCase):
    """RF-3: los trades del motor exponen costes coherentes con las métricas."""

    def test_metrics_match_engine_aggregates(self) -> None:
        candles = walk_forward_dataset(5, _DAY0)
        result = backtest_orb(
            candles,
            OrbBacktestConfig(
                fee_rate=Decimal("0.001"),
                slippage_pct=Decimal("0.05"),
                capital_usd=_CAPITAL,
                hourly_candles=tuple(
                    trend_hourly_flat(count=24 * 8, end=datetime(2026, 3, 8))
                ),
            ),
        )
        self.assertGreater(result.trades, 0)
        self.assertEqual(len(result.trade_list), result.trades)

        metrics = compute_fold_metrics(
            list(result.trade_list),
            _CAPITAL,
            _DAY0,
            _DAY0 + timedelta(days=5),
        )
        self.assertEqual(metrics.net_pnl_usd, result.net_pnl_usd)
        self.assertEqual(metrics.fees_usd, result.fees_usd)
        self.assertEqual(metrics.trades, result.trades)
        self.assertEqual(metrics.winning_trades, result.winning_trades)
        # RF-9: sin float en el agregado monetario.
        self.assertIsInstance(metrics.net_pnl_usd, Decimal)
        self.assertIsInstance(metrics.fees_usd, Decimal)

    def test_config_defaults_match_walk_forward(self) -> None:
        config = WalkForwardConfig(symbols=("BTCUSDT",))
        self.assertEqual(config.fee_rate, Decimal("0.0010"))
        self.assertEqual(config.slippage_pct, Decimal("0.05"))


if __name__ == "__main__":
    unittest.main()
