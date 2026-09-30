from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from app.services.execution_price_service import (
    calculate_buy_execution,
    calculate_sell_execution,
    select_best_execution,
)
from app.services.trade_opportunity_service import (
    calculate_opportunity,
    find_best_opportunity,
)


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
class TradeSample:
    timestamp: datetime
    symbol: str
    buy_exchange: str
    sell_exchange: str
    estimated_profit_usd: Decimal
    estimated_profit_percent: Decimal
    realized_proxy_profit_usd: Decimal
    survived_latency: bool


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


def load_jsonl(path: str | Path) -> list[Snapshot]:
    file_path = Path(path)
    snapshots: list[Snapshot] = []

    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue

            try:
                payload = json.loads(raw)
                timestamp = datetime.fromisoformat(str(payload["timestamp"]))
                snapshots.append(
                    Snapshot(
                        timestamp=timestamp,
                        symbol=str(payload["symbol"]).upper(),
                        quotes=list(payload.get("quotes", [])),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Invalid snapshot on line {line_number}: {exc}"
                ) from exc

    snapshots.sort(key=lambda item: item.timestamp)
    return snapshots


def write_snapshot_jsonl(
    path: str | Path,
    snapshots: Iterable[Snapshot],
) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as handle:
        for snapshot in snapshots:
            payload = {
                "timestamp": snapshot.timestamp.isoformat(),
                "symbol": snapshot.symbol,
                "quotes": snapshot.quotes,
            }
            handle.write(
                json.dumps(payload, default=str, separators=(",", ":"))
                + "\n"
            )


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


def result_to_json(result: BacktestResult) -> str:
    return json.dumps(result.to_dict(), indent=2)