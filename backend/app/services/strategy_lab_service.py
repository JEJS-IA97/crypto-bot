from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from app.domain.orb_engine import (
    CANDLE_MINUTES,
    OrbConfig,
    ny_datetime,
    session_bounds,
)
from app.domain.signal_engine import (
    Candle,
    SignalAction,
    StrategyConfig as SignalConfig,
    evaluate,
)
from app.services.execution_price_service import (
    calculate_buy_execution,
    calculate_sell_execution,
    select_best_execution,
)
from app.services.trade_opportunity_service import (
    find_best_opportunity,
)

FEE_RATE_DEFAULT = Decimal("0.001")
_MONEY_QUANTUM = Decimal("0.00000001")
_PCT_QUANTUM = Decimal("0.01")
_HUNDRED = Decimal("100")


@dataclass(frozen=True)
class StrategyConfig:
    capital_usd: Decimal = Decimal("5")
    min_profit_usd: Decimal = Decimal("0.05")
    min_profit_percent: Decimal = Decimal("0.10")
    taker_slippage_percent: Decimal = Decimal("0.08")
    assumed_latency_seconds: int = 2
    cooldown_seconds: int = 0


@dataclass(frozen=True)
class Snapshot:
    timestamp: datetime
    symbol: str
    quotes: list[dict[str, Any]]


@dataclass(frozen=True)
class BacktestResult:
    config: StrategyConfig
    snapshots: int
    candidates: int
    executable_candidates: int
    profitable_samples: int
    survived_samples: int
    total_proxy_profit_usd: Decimal
    average_proxy_profit_usd: Decimal
    win_rate_percent: Decimal
    max_drawdown_usd: Decimal
    trades_per_snapshot: Decimal

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["config"] = {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in asdict(self.config).items()
        }
        for key, value in list(result.items()):
            if isinstance(value, Decimal):
                result[key] = str(value)
        return result


def normalize_snapshot_quotes(snapshot: Snapshot) -> list[dict[str, Any]]:
    quotes: list[dict[str, Any]] = []

    for quote in snapshot.quotes:
        if quote.get("status") != "ok":
            continue

        normalized = dict(quote)
        for key in (
            "bid_price",
            "bid_quantity",
            "ask_price",
            "ask_quantity",
            "last_price",
            "volume_24h",
        ):
            value = normalized.get(key)
            if value not in (None, ""):
                normalized[key] = Decimal(str(value))

        quotes.append(normalized)

    return quotes


def evaluate_snapshot(
    snapshot: Snapshot,
    config: StrategyConfig,
) -> dict[str, Any] | None:
    quotes = normalize_snapshot_quotes(snapshot)
    executions = select_best_execution(quotes)

    if executions["best_buy"] is None or executions["best_sell"] is None:
        return None

    opportunity_result = find_best_opportunity(
        executions=executions,
        capital_usd=config.capital_usd,
        min_profit_usd=config.min_profit_usd,
        min_profit_percent=config.min_profit_percent,
    )

    opportunity = opportunity_result.get("best_opportunity")
    if opportunity is None:
        return None

    return {
        "snapshot": snapshot,
        "executions": executions,
        "opportunity": opportunity,
    }


def _future_snapshot_after_latency(
    snapshots: list[Snapshot],
    index: int,
    latency_seconds: int,
) -> Snapshot | None:
    if latency_seconds <= 0:
        return snapshots[index]

    target = snapshots[index].timestamp.timestamp() + latency_seconds

    for candidate in snapshots[index + 1 :]:
        if candidate.symbol != snapshots[index].symbol:
            continue
        if candidate.timestamp.timestamp() >= target:
            return candidate

    return None


def _find_execution_at_exchange(
    snapshot: Snapshot,
    exchange: str,
    side: str,
) -> dict[str, Any] | None:
    quotes = normalize_snapshot_quotes(snapshot)

    for quote in quotes:
        if quote.get("exchange") != exchange:
            continue

        if side == "BUY" and quote.get("ask_price") is not None:
            return calculate_buy_execution(quote)

        if side == "SELL" and quote.get("bid_price") is not None:
            return calculate_sell_execution(quote)

    return None


def _locked_future_profit(
    snapshot: Snapshot,
    config: StrategyConfig,
    opportunity: dict[str, Any],
) -> Decimal | None:
    buy_exchange = str(opportunity["buy_exchange"])
    sell_exchange = str(opportunity["sell_exchange"])

    future_buy = _find_execution_at_exchange(
        snapshot=snapshot,
        exchange=buy_exchange,
        side="BUY",
    )
    future_sell = _find_execution_at_exchange(
        snapshot=snapshot,
        exchange=sell_exchange,
        side="SELL",
    )

    if future_buy is None or future_sell is None:
        return None

    if future_buy["quote_currency"] != future_sell["quote_currency"]:
        return None

    quantity = Decimal(str(opportunity["quantity"]))
    capital_used = quantity * Decimal(
        str(future_buy["effective_price_usd"])
    )
    future_sell_value = quantity * Decimal(
        str(future_sell["effective_price_usd"])
    )

    if capital_used <= 0:
        return None

    gross_proxy_profit = future_sell_value - capital_used

    penalty = config.taker_slippage_percent / Decimal("100")
    slippage_cost = (
        Decimal(str(future_buy["effective_price_usd"]))
        + Decimal(str(future_sell["effective_price_usd"]))
    ) * penalty * quantity

    return gross_proxy_profit - slippage_cost


def backtest(
    snapshots: list[Snapshot],
    config: StrategyConfig,
) -> BacktestResult:
    if not snapshots:
        raise ValueError("No snapshots supplied for backtest.")

    equity = Decimal("0")
    peak = Decimal("0")
    max_drawdown = Decimal("0")

    candidates = 0
    executable_candidates = 0
    profitable_samples = 0
    survived_samples = 0

    proxy_profits: list[Decimal] = []
    last_trade_at: dict[str, datetime] = {}

    ordered = sorted(snapshots, key=lambda item: item.timestamp)

    for index, snapshot in enumerate(ordered):
        evaluation = evaluate_snapshot(snapshot, config)
        if evaluation is None:
            continue

        candidates += 1
        opportunity = evaluation["opportunity"]

        estimated_profit = Decimal(
            str(opportunity["estimated_profit_usd"])
        )
        if estimated_profit <= 0:
            continue

        executable_candidates += 1

        previous_trade = last_trade_at.get(snapshot.symbol)
        if previous_trade is not None:
            elapsed = (
                snapshot.timestamp - previous_trade
            ).total_seconds()
            if elapsed < config.cooldown_seconds:
                continue

        profitable_samples += 1

        future_snapshot = _future_snapshot_after_latency(
            ordered,
            index,
            config.assumed_latency_seconds,
        )
        if future_snapshot is None:
            continue

        # Critical realism rule:
        # the future result must use the SAME buy/sell exchanges selected
        # at signal time. We must not re-select the best exchanges after
        # latency, otherwise the backtest introduces look-ahead bias.
        future_profit = _locked_future_profit(
            snapshot=future_snapshot,
            config=config,
            opportunity=opportunity,
        )
        if future_profit is None:
            continue

        last_trade_at[snapshot.symbol] = snapshot.timestamp
        proxy_profits.append(future_profit)

        equity += future_profit
        peak = max(peak, equity)
        max_drawdown = max(
            max_drawdown,
            peak - equity,
        )

        if future_profit > 0:
            survived_samples += 1

    total_proxy = sum(proxy_profits, Decimal("0"))
    average_proxy = (
        total_proxy / Decimal(str(len(proxy_profits)))
        if proxy_profits
        else Decimal("0")
    )

    win_rate = (
        Decimal(str(survived_samples))
        / Decimal(str(len(proxy_profits)))
        * Decimal("100")
        if proxy_profits
        else Decimal("0")
    )

    trades_per_snapshot = (
        Decimal(str(len(proxy_profits)))
        / Decimal(str(len(ordered)))
        if ordered
        else Decimal("0")
    )

    return BacktestResult(
        config=config,
        snapshots=len(ordered),
        candidates=candidates,
        executable_candidates=executable_candidates,
        profitable_samples=profitable_samples,
        survived_samples=survived_samples,
        total_proxy_profit_usd=total_proxy,
        average_proxy_profit_usd=average_proxy,
        win_rate_percent=win_rate,
        max_drawdown_usd=max_drawdown,
        trades_per_snapshot=trades_per_snapshot,
    )


def split_time_series(
    snapshots: list[Snapshot],
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> tuple[list[Snapshot], list[Snapshot], list[Snapshot]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1.")
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1.")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be below 1.")

    ordered = sorted(snapshots, key=lambda item: item.timestamp)
    total = len(ordered)

    if total == 0:
        return [], [], []

    if total == 1:
        return ordered, [], []

    train_end = max(1, int(total * train_ratio))
    train_end = min(train_end, total - 2) if total >= 3 else 1

    if total >= 3:
        validation_size = max(1, int(total * validation_ratio))
        validation_end = min(
            total - 1,
            train_end + validation_size,
        )
        if validation_end <= train_end:
            validation_end = train_end + 1
    else:
        validation_end = total

    return (
        ordered[:train_end],
        ordered[train_end:validation_end],
        ordered[validation_end:],
    )


def grid_search(
    snapshots: list[Snapshot],
    configs: Iterable[StrategyConfig],
) -> list[BacktestResult]:
    results = [backtest(snapshots, config) for config in configs]
    return sorted(
        results,
        key=lambda result: (
            result.total_proxy_profit_usd,
            result.survived_samples,
            result.win_rate_percent,
        ),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Backtest sobre klines históricos (spec 001, RF-15)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KlineBacktestConfig:
    fee_rate: Decimal = FEE_RATE_DEFAULT
    slippage_pct: Decimal = Decimal("0")
    capital_usd: Decimal = Decimal("20")

    def __post_init__(self) -> None:
        for name in ("fee_rate", "slippage_pct", "capital_usd"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be a Decimal")
        if self.fee_rate < 0:
            raise ValueError("fee_rate must be >= 0")
        if self.slippage_pct < 0:
            raise ValueError("slippage_pct must be >= 0")
        if self.capital_usd <= 0:
            raise ValueError("capital_usd must be > 0")


@dataclass(frozen=True)
class KlineTrade:
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    fees_usd: Decimal
    pnl_usd: Decimal


@dataclass(frozen=True)
class KlineBacktestResult:
    strategy: dict[str, Any]
    candles: int
    trades: int
    winning_trades: int
    net_pnl_usd: Decimal
    return_pct: Decimal
    max_drawdown_usd: Decimal
    max_drawdown_pct: Decimal
    win_rate_pct: Decimal
    fees_usd: Decimal

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in asdict(self).items():
            if key == "strategy":
                result[key] = {
                    sub_key: (
                        str(sub_value)
                        if isinstance(sub_value, Decimal)
                        else sub_value
                    )
                    for sub_key, sub_value in value.items()
                }
            elif isinstance(value, Decimal):
                result[key] = str(value)
            else:
                result[key] = value
        return result


def load_klines_jsonl(path: str | Path) -> list[Candle]:
    """Carga klines en el JSONL producido por ``collect_klines.py`` (T14)."""
    file_path = Path(path)
    candles: list[Candle] = []

    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue

            try:
                payload = json.loads(raw)
                open_time = datetime.fromtimestamp(
                    int(payload["open_time"]) / 1000,
                    tz=timezone.utc,
                ).replace(tzinfo=None)
                candles.append(
                    Candle(
                        open_time=open_time,
                        open=Decimal(str(payload["open"])),
                        high=Decimal(str(payload["high"])),
                        low=Decimal(str(payload["low"])),
                        close=Decimal(str(payload["close"])),
                        volume=Decimal(str(payload["volume"])),
                    )
                )
            except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
                raise ValueError(
                    f"Invalid kline on line {line_number}: {exc}"
                ) from exc

    candles.sort(key=lambda item: item.open_time)
    return candles


def split_candles(
    candles: list[Candle],
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> tuple[list[Candle], list[Candle], list[Candle]]:
    """Split cronológico (sin look-ahead) train / validation / test."""
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1.")
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1.")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be below 1.")

    ordered = sorted(candles, key=lambda item: item.open_time)
    total = len(ordered)

    if total == 0:
        return [], [], []

    if total == 1:
        return ordered, [], []

    train_end = max(1, int(total * train_ratio))
    train_end = min(train_end, total - 2) if total >= 3 else 1

    if total >= 3:
        validation_size = max(1, int(total * validation_ratio))
        validation_end = min(
            total - 1,
            train_end + validation_size,
        )
        if validation_end <= train_end:
            validation_end = train_end + 1
    else:
        validation_end = total

    return (
        ordered[:train_end],
        ordered[train_end:validation_end],
        ordered[validation_end:],
    )


def backtest_candles(
    candles: list[Candle],
    strategy: SignalConfig,
    config: KlineBacktestConfig | None = None,
) -> KlineBacktestResult:
    """Backtest de la estrategia de señales sobre klines históricos.

    Se decide con las velas hasta el cierre anterior (``ordered[:index]``)
    y se ejecuta en la apertura de la vela actual: sin look-ahead.
    Sólo largos (venta = cierre de la posición; sin posición la señal se
    ignora) y costes reales: comisión ``fee_rate`` por lado y deslizamiento
    ``slippage_pct`` configurable en la entrada y en la salida.
    """
    if not candles:
        raise ValueError("No klines supplied for backtest.")
    if config is None:
        config = KlineBacktestConfig()

    ordered = sorted(candles, key=lambda item: item.open_time)
    slip = config.slippage_pct / _HUNDRED
    fee_rate = config.fee_rate
    capital = config.capital_usd

    trades: list[KlineTrade] = []
    open_position: dict[str, Any] | None = None
    equity = capital
    peak = capital
    max_drawdown_usd = Decimal("0")
    max_drawdown_pct = Decimal("0")

    def _close_position(
        position: dict[str, Any],
        exit_time: datetime,
        exit_reference: Decimal,
    ) -> None:
        nonlocal open_position, equity, peak
        nonlocal max_drawdown_usd, max_drawdown_pct

        exit_fill = exit_reference * (Decimal("1") - slip)
        proceeds = position["quantity"] * exit_fill
        exit_fee = proceeds * fee_rate
        pnl = (
            proceeds
            - exit_fee
            - position["entry_cost"]
            - position["entry_fee"]
        )
        trades.append(
            KlineTrade(
                entry_time=position["entry_time"],
                exit_time=exit_time,
                entry_price=position["entry_fill"],
                exit_price=exit_fill,
                quantity=position["quantity"],
                fees_usd=position["entry_fee"] + exit_fee,
                pnl_usd=pnl,
            )
        )

        equity += pnl
        peak = max(peak, equity)
        drawdown_usd = peak - equity
        if drawdown_usd > max_drawdown_usd:
            max_drawdown_usd = drawdown_usd
            max_drawdown_pct = (
                drawdown_usd * _HUNDRED / peak if peak > 0 else Decimal("0")
            )

        open_position = None

    for index in range(1, len(ordered)):
        candle = ordered[index]
        signal = evaluate(ordered[:index], strategy)

        if signal.action == SignalAction.BUY and open_position is None:
            entry_fill = candle.open * (Decimal("1") + slip)
            quantity = capital / entry_fill
            entry_cost = quantity * entry_fill
            open_position = {
                "entry_time": candle.open_time,
                "entry_fill": entry_fill,
                "quantity": quantity,
                "entry_cost": entry_cost,
                "entry_fee": entry_cost * fee_rate,
            }
        elif signal.action == SignalAction.SELL and open_position is not None:
            _close_position(open_position, candle.open_time, candle.open)

    if open_position is not None:
        _close_position(open_position, ordered[-1].open_time, ordered[-1].close)

    winning = sum(1 for trade in trades if trade.pnl_usd > 0)
    net_pnl = sum((trade.pnl_usd for trade in trades), Decimal("0"))
    fees = sum((trade.fees_usd for trade in trades), Decimal("0"))

    return KlineBacktestResult(
        strategy=asdict(strategy),
        candles=len(ordered),
        trades=len(trades),
        winning_trades=winning,
        net_pnl_usd=net_pnl.quantize(_MONEY_QUANTUM),
        return_pct=(net_pnl * _HUNDRED / capital).quantize(_PCT_QUANTUM),
        max_drawdown_usd=max_drawdown_usd.quantize(_MONEY_QUANTUM),
        max_drawdown_pct=max_drawdown_pct.quantize(_PCT_QUANTUM),
        win_rate_pct=(
            Decimal(str(winning)) / Decimal(str(len(trades))) * _HUNDRED
            if trades
            else Decimal("0")
        ).quantize(_PCT_QUANTUM),
        fees_usd=fees.quantize(_MONEY_QUANTUM),
    )


def grid_search_candles(
    candles: list[Candle],
    strategies: Iterable[SignalConfig],
    config: KlineBacktestConfig | None = None,
) -> list[KlineBacktestResult]:
    results = [
        backtest_candles(candles, strategy, config)
        for strategy in strategies
    ]
    return sorted(
        results,
        key=lambda result: (
            result.net_pnl_usd,
            result.win_rate_pct,
            -result.max_drawdown_pct,
        ),
        reverse=True,
    )


@dataclass(frozen=True)
class OrbBacktestConfig:
    """Costes y salidas del backtest ORB (RF-15, D-11: TP/SL 1:1)."""

    fee_rate: Decimal = FEE_RATE_DEFAULT
    slippage_pct: Decimal = Decimal("0")
    capital_usd: Decimal = Decimal("20")
    stop_loss_pct: Decimal = Decimal("2.0")
    take_profit_pct: Decimal = Decimal("2.0")
    orb: OrbConfig = OrbConfig()

    def __post_init__(self) -> None:
        for name in (
            "fee_rate",
            "slippage_pct",
            "capital_usd",
            "stop_loss_pct",
            "take_profit_pct",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be a Decimal")
        if self.fee_rate < 0:
            raise ValueError("fee_rate must be >= 0")
        if self.slippage_pct < 0:
            raise ValueError("slippage_pct must be >= 0")
        if self.capital_usd <= 0:
            raise ValueError("capital_usd must be > 0")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be > 0")
        if self.take_profit_pct <= 0:
            raise ValueError("take_profit_pct must be > 0")
        if not isinstance(self.orb, OrbConfig):
            raise TypeError("orb must be an OrbConfig")


def backtest_orb(
    candles: list[Candle],
    config: OrbBacktestConfig | None = None,
) -> KlineBacktestResult:
    """Backtest ORB sobre klines 5m (RF-15).

    Por cada día de Nueva York con las 6 velas del rango (9:00–9:30 AM NY,
    si falta alguna el día se ignora, fail-closed): la primera vela 9:30–10:00
    cuyo cierre supera el alto del rango entra en largo con la referencia de
    su cierre, y sólo una entrada al día (RF-27). La posición sale por SL/TP
    (``stop_loss_pct``/``take_profit_pct``, D-11) o al cerrar la ventana con
    el cierre de la última vela de 9:55 AM NY. Sólo se usan velas abiertas
    dentro de la ventana: sin look-ahead. Costes: comisión ``fee_rate`` por
    lado y deslizamiento ``slippage_pct`` configurable en entrada y salida.
    """
    if not candles:
        raise ValueError("No klines supplied for backtest.")
    active = config if config is not None else OrbBacktestConfig()

    ordered = sorted(candles, key=lambda item: item.open_time)
    slip = active.slippage_pct / _HUNDRED
    fee_rate = active.fee_rate
    capital = active.capital_usd
    stop_distance = active.stop_loss_pct / _HUNDRED
    target_distance = active.take_profit_pct / _HUNDRED

    trades: list[KlineTrade] = []
    open_position: dict[str, Any] | None = None
    equity = capital
    peak = capital
    max_drawdown_usd = Decimal("0")
    max_drawdown_pct = Decimal("0")

    def _close_position(
        position: dict[str, Any],
        exit_time: datetime,
        exit_reference: Decimal,
    ) -> None:
        nonlocal open_position, equity, peak
        nonlocal max_drawdown_usd, max_drawdown_pct

        exit_fill = exit_reference * (Decimal("1") - slip)
        proceeds = position["quantity"] * exit_fill
        exit_fee = proceeds * fee_rate
        pnl = (
            proceeds
            - exit_fee
            - position["entry_cost"]
            - position["entry_fee"]
        )
        trades.append(
            KlineTrade(
                entry_time=position["entry_time"],
                exit_time=exit_time,
                entry_price=position["entry_fill"],
                exit_price=exit_fill,
                quantity=position["quantity"],
                fees_usd=position["entry_fee"] + exit_fee,
                pnl_usd=pnl,
            )
        )

        equity += pnl
        peak = max(peak, equity)
        drawdown_usd = peak - equity
        if drawdown_usd > max_drawdown_usd:
            max_drawdown_usd = drawdown_usd
            max_drawdown_pct = (
                drawdown_usd * _HUNDRED / peak if peak > 0 else Decimal("0")
            )

        open_position = None

    by_day: dict[date, list[Candle]] = {}
    for candle in ordered:
        ny_day = ny_datetime(candle.open_time, active.orb).date()
        by_day.setdefault(ny_day, []).append(candle)

    for ny_day in sorted(by_day):
        range_open, range_close, window_close = session_bounds(
            ny_day, active.orb
        )
        expected_opens = [
            range_open + timedelta(minutes=CANDLE_MINUTES * index)
            for index in range(active.orb.range_minutes // CANDLE_MINUTES)
        ]
        by_open_ny = {
            ny_datetime(candle.open_time, active.orb): candle
            for candle in by_day[ny_day]
        }
        if any(moment not in by_open_ny for moment in expected_opens):
            continue  # rango incompleto: el día se ignora (fail-closed)

        range_high = max(by_open_ny[moment].high for moment in expected_opens)

        session = sorted(
            (
                candle
                for candle in by_day[ny_day]
                if range_open
                <= ny_datetime(candle.open_time, active.orb)
                < window_close
            ),
            key=lambda item: item.open_time,
        )
        entered_today = False

        for index, candle in enumerate(session):
            open_ny = ny_datetime(candle.open_time, active.orb)
            if open_ny < range_close:
                continue  # velas del rango: sólo construyen el rango

            is_last_window_candle = index == len(session) - 1

            if open_position is None:
                if not entered_today and candle.close > range_high:
                    entry_fill = candle.close * (Decimal("1") + slip)
                    quantity = capital / entry_fill
                    entry_cost = quantity * entry_fill
                    open_position = {
                        "entry_time": candle.open_time,
                        "entry_fill": entry_fill,
                        "quantity": quantity,
                        "entry_cost": entry_cost,
                        "entry_fee": entry_cost * fee_rate,
                        "stop": entry_fill * (Decimal("1") - stop_distance),
                        "target": entry_fill * (Decimal("1") + target_distance),
                    }
                    entered_today = True
            else:
                # El SL se comprueba antes que el TP (conservador).
                if candle.low <= open_position["stop"]:
                    _close_position(
                        open_position, candle.open_time, open_position["stop"]
                    )
                elif candle.high >= open_position["target"]:
                    _close_position(
                        open_position,
                        candle.open_time,
                        open_position["target"],
                    )

            # Cierre forzado al terminar la ventana del día.
            if open_position is not None and is_last_window_candle:
                _close_position(
                    open_position, candle.open_time, candle.close
                )

    winning = sum(1 for trade in trades if trade.pnl_usd > 0)
    net_pnl = sum((trade.pnl_usd for trade in trades), Decimal("0"))
    fees = sum((trade.fees_usd for trade in trades), Decimal("0"))

    return KlineBacktestResult(
        strategy=asdict(active),
        candles=len(ordered),
        trades=len(trades),
        winning_trades=winning,
        net_pnl_usd=net_pnl.quantize(_MONEY_QUANTUM),
        return_pct=(net_pnl * _HUNDRED / capital).quantize(_PCT_QUANTUM),
        max_drawdown_usd=max_drawdown_usd.quantize(_MONEY_QUANTUM),
        max_drawdown_pct=max_drawdown_pct.quantize(_PCT_QUANTUM),
        win_rate_pct=(
            Decimal(str(winning)) / Decimal(str(len(trades))) * _HUNDRED
            if trades
            else Decimal("0")
        ).quantize(_PCT_QUANTUM),
        fees_usd=fees.quantize(_MONEY_QUANTUM),
    )


def grid_search_orb(
    candles: list[Candle],
    configs: Iterable[OrbBacktestConfig],
) -> list[KlineBacktestResult]:
    results = [backtest_orb(candles, config) for config in configs]
    return sorted(
        results,
        key=lambda result: (
            result.net_pnl_usd,
            result.win_rate_pct,
            -result.max_drawdown_pct,
        ),
        reverse=True,
    )


def final_parameters_section(
    strategy: SignalConfig,
    kline_config: KlineBacktestConfig,
    metrics: dict[str, Any] | None = None,
    notes: Iterable[str] | None = None,
    generated_at: datetime | None = None,
) -> str:
    stamp = (generated_at or datetime.now(timezone.utc)).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    lines = [
        "## Parámetros finales (duda abierta #1)",
        "",
        f"> Generado por `train_strategy.py` el {stamp} sobre"
        " `data/klines/*.jsonl`.",
        "> Backtest con comisión y slippage por lado, split cronológico"
        " train/valid/test sin look-ahead (RF-15).",
        "",
        "| Parámetro | Valor |",
        "| --- | --- |",
    ]
    for key, value in asdict(strategy).items():
        lines.append(f"| {key} | {value} |")
    lines.append(f"| fee_rate | {kline_config.fee_rate} |")
    lines.append(f"| slippage_pct | {kline_config.slippage_pct} |")
    lines.append(f"| capital_usd | {kline_config.capital_usd} |")

    if metrics:
        lines += [
            "",
            "| Métrica | Valor |",
            "| --- | --- |",
        ]
        for key, value in metrics.items():
            lines.append(f"| {key} | {value} |")

    for note in notes or []:
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def write_final_parameters(
    plan_path: str | Path,
    *,
    strategy: SignalConfig,
    kline_config: KlineBacktestConfig,
    metrics: dict[str, Any] | None = None,
    notes: Iterable[str] | None = None,
    generated_at: datetime | None = None,
) -> None:
    """Escribe (o reemplaza) la sección de parámetros finales en el plan."""
    path = Path(plan_path)
    section = final_parameters_section(
        strategy=strategy,
        kline_config=kline_config,
        metrics=metrics,
        notes=notes,
        generated_at=generated_at,
    )

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "## Parámetros finales"
    start = text.find(marker)

    if start == -1:
        new_text = text.rstrip("\n") + "\n\n" + section
    else:
        rest = text[start:]
        next_heading = rest.find("\n## ", 1)
        if next_heading == -1:
            new_text = text[:start] + section
        else:
            new_text = text[:start] + section + rest[next_heading + 1 :]

    path.write_text(new_text, encoding="utf-8")