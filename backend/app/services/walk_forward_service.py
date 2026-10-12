"""Walk-forward ORB (spec 011): folds, validación, grid y selección train/valid.

Módulo puro (sin BD, sin red, sin runtime del bot). Reutiliza el motor
de backtest ORB de ``strategy_lab_service`` sin modificar su lógica.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

from app.domain.signal_engine import Candle
from app.services.strategy_lab_service import (
    KlineTrade,
    OrbBacktestConfig,
    backtest_orb,
    load_klines_jsonl,
)

_MAX_LOSS_PER_TRADE_USD = Decimal("1")
_HUNDRED = Decimal("100")
_MONEY_QUANTUM = Decimal("0.00000001")  # alineado con strategy_lab_service
_PCT_QUANTUM = Decimal("0.01")
_RATIO_QUANTUM = Decimal("0.0001")
_SHARPE_QUANTUM = Decimal("0.0001")
_ANNUALIZATION = Decimal("252")


@dataclass(frozen=True)
class WalkForwardConfig:
    """Parámetros de una corrida walk-forward (plan D-3/D-4)."""

    symbols: tuple[str, ...]
    interval: str = "5m"
    train_days: int = 180
    test_days: int = 30
    step_days: int = 30
    validation_ratio: float = 0.15
    fee_rate: Decimal = Decimal("0.0010")
    slippage_pct: Decimal = Decimal("0.05")
    capital_usd: Decimal = Decimal("20")
    stop_loss_grid: tuple[Decimal, ...] = (
        Decimal("1.0"),
        Decimal("1.5"),
        Decimal("2.0"),
    )
    take_profit_grid: tuple[Decimal, ...] = (
        Decimal("1.0"),
        Decimal("1.5"),
        Decimal("2.0"),
    )
    data_dir: Path = Path("data/klines")
    # Spec 012, D-8: velas 1h para el filtro de tendencia del backtest
    # (RF-2/RF-3). Sin archivos aquí el filtro es fail-closed.
    hourly_dir: Path = Path("data/klines_1h")

    def __post_init__(self) -> None:
        if not self.symbols or any(not s for s in self.symbols):
            raise ValueError("symbols must be a non-empty tuple")
        if self.interval != "5m":
            raise ValueError("interval must be '5m' for ORB (D-2)")
        if not isinstance(self.data_dir, Path) or not isinstance(
            self.hourly_dir, Path
        ):
            raise TypeError("data_dir and hourly_dir must be Path")
        for name in ("train_days", "test_days", "step_days"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be int")
            if value <= 0:
                raise ValueError(f"{name} must be > 0")
        if not 0 < self.validation_ratio < 1:
            raise ValueError("validation_ratio must be between 0 and 1")
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
        if not self.stop_loss_grid or not self.take_profit_grid:
            raise ValueError("grid values must be non-empty")
        for value in (*self.stop_loss_grid, *self.take_profit_grid):
            if not isinstance(value, Decimal) or value <= 0:
                raise ValueError("grid values must be positive Decimals")


@dataclass(frozen=True)
class FoldWindow:
    """Un fold: train [train_start, train_end) + test [test_start, test_end)."""

    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date


def validate_candles(candles: Sequence[Candle]) -> None:
    """Validación mínima D-8: orden estricto y OHLC consistente."""
    if not candles:
        raise ValueError("candles must be non-empty")
    previous: datetime | None = None
    for candle in candles:
        if not isinstance(candle.open_time, datetime):
            raise TypeError("candle.open_time must be a datetime")
        if previous is not None and candle.open_time <= previous:
            raise ValueError("candle open_time must be strictly increasing")
        previous = candle.open_time
        if candle.low > min(candle.open, candle.close):
            raise ValueError("candle low must be <= min(open, close)")
        if candle.high < max(candle.open, candle.close):
            raise ValueError("candle high must be >= max(open, close)")


def build_folds(
    candles_by_symbol: Mapping[str, list[Candle]],
    config: WalkForwardConfig,
) -> list[FoldWindow]:
    """Construye los folds rodantes exactos de D-3 sobre el span total."""
    if not candles_by_symbol:
        raise ValueError("candles_by_symbol must not be empty")
    earliest: Candle | None = None
    latest: Candle | None = None
    for symbol, candles in candles_by_symbol.items():
        if not symbol:
            raise ValueError("symbol names must be non-empty")
        if not candles:
            raise ValueError(f"no klines for symbol {symbol!r}")
        validate_candles(candles)
        if earliest is None or candles[0].open_time < earliest.open_time:
            earliest = candles[0]
        if latest is None or candles[-1].open_time > latest.open_time:
            latest = candles[-1]

    assert earliest is not None and latest is not None
    start_day: date = earliest.open_time.date()
    last_day: date = latest.open_time.date()
    span_days = (last_day - start_day).days + 1

    folds: list[FoldWindow] = []
    index = 0
    while True:
        train_start = start_day + timedelta(days=index * config.step_days)
        train_end = train_start + timedelta(days=config.train_days)
        test_end = train_end + timedelta(days=config.test_days)
        if (test_end - start_day).days > span_days:
            break
        folds.append(
            FoldWindow(
                index=index,
                train_start=train_start,
                train_end=train_end,
                test_start=train_end,
                test_end=test_end,
            )
        )
        index += 1

    if not folds:
        raise ValueError(
            "dataset insuficiente: no cabe ni un fold "
            f"({config.train_days + config.test_days} días requeridos)"
        )
    return folds


def candles_in_range(
    candles: Sequence[Candle],
    start: date,
    end: date,
) -> list[Candle]:
    """Velas cuyo ``open_time`` cae en [start, end) (fechas, fin exclusivo)."""
    return [
        candle
        for candle in candles
        if start <= candle.open_time.date() < end
    ]


def split_train_validation(
    train: Sequence[Candle],
    ratio: float,
) -> tuple[list[Candle], list[Candle]]:
    """Última fracción ``ratio`` del train como validación (const. #9)."""
    if not 0 < ratio < 1:
        raise ValueError("ratio must be between 0 and 1")
    total = len(train)
    if total < 2:
        raise ValueError("train needs at least 2 candles to split")
    validation_size = max(1, int(total * ratio))
    train_part = list(train[:-validation_size])
    validation = list(train[-validation_size:])
    if not train_part:
        raise ValueError("train part must not be empty")
    return train_part, validation


def iter_grid(config: WalkForwardConfig) -> list[OrbBacktestConfig]:
    """Candidatos SL×TP; descarta los que superen 1 USD de pérdida (const. #3)."""
    candidates: list[OrbBacktestConfig] = []
    for stop_loss in config.stop_loss_grid:
        max_loss = config.capital_usd * stop_loss / _HUNDRED
        if max_loss > _MAX_LOSS_PER_TRADE_USD:
            continue
        for take_profit in config.take_profit_grid:
            candidates.append(
                OrbBacktestConfig(
                    fee_rate=config.fee_rate,
                    slippage_pct=config.slippage_pct,
                    capital_usd=config.capital_usd,
                    stop_loss_pct=stop_loss,
                    take_profit_pct=take_profit,
                )
            )
    if not candidates:
        raise ValueError("grid produced no valid candidates")
    return candidates


def select_params(
    train: Sequence[Candle],
    validation: Sequence[Candle],
    config: WalkForwardConfig,
    hourly: Sequence[Candle] | None = None,
) -> tuple[Decimal, Decimal]:
    """Mejor (SL, TP) por PnL de validación; empate ⇒ menor SL, luego TP."""
    scored = list(validation) if validation else list(train)
    if not scored:
        raise ValueError("no candles to score the grid")
    hourly_by_symbol = {"_single_": list(hourly)} if hourly is not None else None
    return select_params_by_symbol(
        {"_single_": list(train)},
        {"_single_": scored},
        config,
        hourly_by_symbol=hourly_by_symbol,
    )


def select_params_by_symbol(
    train_by_symbol: Mapping[str, Sequence[Candle]],
    validation_by_symbol: Mapping[str, Sequence[Candle]],
    config: WalkForwardConfig,
    hourly_by_symbol: Mapping[str, Sequence[Candle]] | None = None,
) -> tuple[Decimal, Decimal]:
    """Selección global: suma el PnL de validación de todos los símbolos."""
    pairs = [
        (
            list(validation_by_symbol.get(symbol, ())) or list(train),
            symbol,
        )
        for symbol, train in train_by_symbol.items()
    ]
    pairs = [(scored, symbol) for scored, symbol in pairs if scored]
    if not pairs:
        raise ValueError("no candles to score the grid")

    hourly_map = hourly_by_symbol or {}
    best: OrbBacktestConfig | None = None
    best_key: tuple[Decimal, Decimal, Decimal] | None = None
    for candidate in iter_grid(config):
        total = Decimal("0")
        for scored, symbol in pairs:
            scored_config = replace(
                candidate,
                hourly_candles=tuple(hourly_map.get(symbol, ())),
            )
            total += backtest_orb(list(scored), scored_config).net_pnl_usd
        key = (
            total,
            -candidate.stop_loss_pct,
            -candidate.take_profit_pct,
        )
        if best_key is None or key > best_key:
            best = candidate
            best_key = key

    assert best is not None
    return best.stop_loss_pct, best.take_profit_pct


@dataclass(frozen=True)
class FoldMetrics:
    """Las 5 métricas de la spec (RF-4) más conteos y brutos (para el agregado)."""

    net_pnl_usd: Decimal
    return_pct: Decimal
    max_drawdown_usd: Decimal
    max_drawdown_pct: Decimal
    sharpe: Decimal
    profit_factor: Decimal | None
    expectancy_usd: Decimal
    trades: int
    winning_trades: int
    fees_usd: Decimal
    gross_profit_usd: Decimal
    gross_loss_usd: Decimal  # valor absoluto de la suma de pérdidas


def daily_equity_series(
    trades: Sequence[KlineTrade],
    capital: Decimal,
    start: date,
    end: date,
) -> list[Decimal]:
    """Equity al cierre de cada día calendario [start, end); días planos heredan."""
    by_day: dict[date, Decimal] = {}
    equity = capital
    for trade in sorted(trades, key=lambda item: item.exit_time):
        equity += trade.pnl_usd
        by_day[trade.exit_time.date()] = equity

    series: list[Decimal] = []
    current = capital
    day = start
    while day < end:
        if day in by_day:
            current = by_day[day]
        series.append(current)
        day += timedelta(days=1)
    return series


def daily_returns(
    equity_by_day: Sequence[Decimal],
    capital: Decimal,
) -> list[Decimal]:
    """Retorno de cada día frente al equity del día anterior (inicio: capital)."""
    returns: list[Decimal] = []
    previous = capital
    for equity in equity_by_day:
        if previous == 0:
            returns.append(Decimal("0"))
        else:
            returns.append((equity - previous) / previous)
        previous = equity
    return returns


def daily_sharpe(returns: Sequence[Decimal]) -> Decimal:
    """Media ÷ desv poblacional × √252 (D-5); <2 retornos o desv 0 ⇒ 0."""
    if len(returns) < 2:
        return Decimal("0")
    total = len(returns)
    mean = sum(returns, Decimal("0")) / Decimal(str(total))
    variance = (
        sum(((item - mean) ** 2 for item in returns), Decimal("0"))
        / Decimal(str(total))
    )
    if variance == 0:
        return Decimal("0")
    std = variance.sqrt()
    return (mean / std * _ANNUALIZATION.sqrt()).quantize(_SHARPE_QUANTUM)


def max_drawdown(equity_curve: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
    """Drawdown máximo (USD, % del pico) sobre la curva de equity."""
    if not equity_curve:
        return Decimal("0"), Decimal("0")
    peak = equity_curve[0]
    worst_usd = Decimal("0")
    worst_pct = Decimal("0")
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = peak - value
        if drawdown > worst_usd:
            worst_usd = drawdown
            worst_pct = (
                drawdown * _HUNDRED / peak if peak != 0 else Decimal("0")
            )
    return worst_usd.quantize(_MONEY_QUANTUM), worst_pct.quantize(_PCT_QUANTUM)


def compute_fold_metrics(
    trades: Sequence[KlineTrade],
    capital: Decimal,
    start: date,
    end: date,
) -> FoldMetrics:
    """Las 5 métricas (RF-4) para un test, desde sus trades y rango de días."""
    pnls = [trade.pnl_usd for trade in trades]
    total_pnl = sum(pnls, Decimal("0"))
    gross_profit = sum((p for p in pnls if p > 0), Decimal("0"))
    gross_loss = abs(sum((p for p in pnls if p < 0), Decimal("0")))
    fees = sum((trade.fees_usd for trade in trades), Decimal("0"))
    winners = sum(1 for p in pnls if p > 0)

    equity_curve = [capital]
    running = capital
    for pnl in pnls:
        running += pnl
        equity_curve.append(running)
    drawdown_usd, drawdown_pct = max_drawdown(equity_curve)

    daily = daily_equity_series(trades, capital, start, end)
    sharpe = daily_sharpe(daily_returns(daily, capital))

    return FoldMetrics(
        net_pnl_usd=total_pnl.quantize(_MONEY_QUANTUM),
        return_pct=(total_pnl * _HUNDRED / capital).quantize(_PCT_QUANTUM),
        max_drawdown_usd=drawdown_usd,
        max_drawdown_pct=drawdown_pct,
        sharpe=sharpe,
        profit_factor=(
            (gross_profit / gross_loss).quantize(_RATIO_QUANTUM)
            if gross_loss > 0
            else None
        ),
        expectancy_usd=(
            (total_pnl / Decimal(str(len(trades)))).quantize(_MONEY_QUANTUM)
            if trades
            else Decimal("0")
        ),
        trades=len(trades),
        winning_trades=winners,
        fees_usd=fees.quantize(_MONEY_QUANTUM),
        gross_profit_usd=gross_profit.quantize(_MONEY_QUANTUM),
        gross_loss_usd=gross_loss.quantize(_MONEY_QUANTUM),
    )


def aggregate_metrics(
    fold_metrics: Sequence[FoldMetrics],
    fold_returns: Sequence[Sequence[Decimal]],
    capital: Decimal,
) -> FoldMetrics:
    """Agregado out-of-sample: suma aritmética de PnL (D-7), Sharpe unido."""
    if not fold_metrics:
        raise ValueError("fold_metrics must not be empty")

    net = sum((m.net_pnl_usd for m in fold_metrics), Decimal("0"))
    fees = sum((m.fees_usd for m in fold_metrics), Decimal("0"))
    gross_profit = sum(
        (m.gross_profit_usd for m in fold_metrics), Decimal("0")
    )
    gross_loss = sum((m.gross_loss_usd for m in fold_metrics), Decimal("0"))
    trades = sum(m.trades for m in fold_metrics)
    winners = sum(m.winning_trades for m in fold_metrics)
    windows = Decimal(str(len(fold_metrics)))

    worst = max(fold_metrics, key=lambda m: m.max_drawdown_usd)
    joined_returns = [
        item for series in fold_returns for item in series
    ]

    return FoldMetrics(
        net_pnl_usd=net.quantize(_MONEY_QUANTUM),
        return_pct=((net * _HUNDRED) / (capital * windows)).quantize(
            _PCT_QUANTUM
        ),
        max_drawdown_usd=worst.max_drawdown_usd,
        max_drawdown_pct=worst.max_drawdown_pct,
        sharpe=daily_sharpe(joined_returns),
        profit_factor=(
            (gross_profit / gross_loss).quantize(_RATIO_QUANTUM)
            if gross_loss > 0
            else None
        ),
        expectancy_usd=(
            (net / Decimal(str(trades))).quantize(_MONEY_QUANTUM)
            if trades
            else Decimal("0")
        ),
        trades=trades,
        winning_trades=winners,
        fees_usd=fees.quantize(_MONEY_QUANTUM),
        gross_profit_usd=gross_profit.quantize(_MONEY_QUANTUM),
        gross_loss_usd=gross_loss.quantize(_MONEY_QUANTUM),
    )


@dataclass(frozen=True)
class FoldResult:
    """Resultado de un fold: parámetros ganadores + métricas del test."""

    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    best_stop_loss_pct: Decimal
    best_take_profit_pct: Decimal
    train_trades: int
    validation_pnl_usd: Decimal
    metrics: FoldMetrics


@dataclass(frozen=True)
class WalkForwardResult:
    """Corrida completa: folds, agregado, buy & hold y veredicto."""

    config: WalkForwardConfig
    folds: tuple[FoldResult, ...]
    aggregate: FoldMetrics
    buy_hold_usd: dict[str, Decimal]
    verdict: str  # "PASA" | "NO PASA"


def load_dataset(config: WalkForwardConfig) -> dict[str, list[Candle]]:
    """Carga y valida los JSONL de ``config.data_dir`` (fail-closed, D-8)."""
    dataset: dict[str, list[Candle]] = {}
    for symbol in config.symbols:
        path = config.data_dir / f"{symbol}.jsonl"
        if not path.exists():
            raise ValueError(f"missing klines file: {path}")
        candles = load_klines_jsonl(path)
        validate_candles(candles)
        dataset[symbol] = candles
    return dataset


def load_hourly_dataset(
    config: WalkForwardConfig,
) -> dict[str, list[Candle]]:
    """Carga las velas 1h de ``config.hourly_dir`` (spec 012, D-8).

    Falta el archivo ⇒ error claro (fail-closed): sin 1h el filtro de
    tendencia no puede evaluar y una corrida con el filtro apagado daría
    un veredicto engañoso.
    """
    dataset: dict[str, list[Candle]] = {}
    for symbol in config.symbols:
        path = config.hourly_dir / f"{symbol}.jsonl"
        if not path.exists():
            raise ValueError(f"missing hourly klines file: {path}")
        candles = load_klines_jsonl(path)
        validate_candles(candles)
        dataset[symbol] = candles
    return dataset


def _orb_config(
    config: WalkForwardConfig,
    stop_loss: Decimal,
    take_profit: Decimal,
) -> OrbBacktestConfig:
    return OrbBacktestConfig(
        fee_rate=config.fee_rate,
        slippage_pct=config.slippage_pct,
        capital_usd=config.capital_usd,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
    )


def _pooled_test_trades(
    dataset: Mapping[str, Sequence[Candle]],
    fold: FoldWindow,
    orb_config: OrbBacktestConfig,
    hourly_by_symbol: Mapping[str, Sequence[Candle]] | None = None,
) -> list[KlineTrade]:
    hourly_map = hourly_by_symbol or {}
    trades: list[KlineTrade] = []
    for symbol in sorted(dataset):
        sliced = candles_in_range(
            dataset[symbol], fold.test_start, fold.test_end
        )
        if not sliced:
            continue
        symbol_config = replace(
            orb_config, hourly_candles=tuple(hourly_map.get(symbol, ()))
        )
        result = backtest_orb(list(sliced), symbol_config)
        trades.extend(result.trade_list)
    return trades


def run_walk_forward(config: WalkForwardConfig) -> WalkForwardResult:
    """Corrida completa (RF-2 a RF-6): folds, selección, gate y agregado."""
    dataset = load_dataset(config)
    hourly_dataset = load_hourly_dataset(config)
    folds = build_folds(dataset, config)

    fold_results: list[FoldResult] = []
    fold_metrics: list[FoldMetrics] = []
    fold_returns: list[list[Decimal]] = []

    for fold in folds:
        train_by_symbol: dict[str, list[Candle]] = {}
        validation_by_symbol: dict[str, list[Candle]] = {}
        for symbol in sorted(dataset):
            train_slice = candles_in_range(
                dataset[symbol], fold.train_start, fold.train_end
            )
            train_part, validation = split_train_validation(
                train_slice, config.validation_ratio
            )
            train_by_symbol[symbol] = train_part
            validation_by_symbol[symbol] = validation

        stop_loss, take_profit = select_params_by_symbol(
            train_by_symbol,
            validation_by_symbol,
            config,
            hourly_by_symbol=hourly_dataset,
        )
        orb_config = _orb_config(config, stop_loss, take_profit)

        validation_pnl = Decimal("0")
        train_trades = 0
        for symbol in sorted(dataset):
            symbol_config = replace(
                orb_config,
                hourly_candles=tuple(hourly_dataset[symbol]),
            )
            validation_result = backtest_orb(
                list(validation_by_symbol[symbol]), symbol_config
            )
            validation_pnl += validation_result.net_pnl_usd
            train_slice = candles_in_range(
                dataset[symbol], fold.train_start, fold.train_end
            )
            train_trades += backtest_orb(
                train_slice, symbol_config
            ).trades

        test_trades = _pooled_test_trades(
            dataset, fold, orb_config, hourly_by_symbol=hourly_dataset
        )
        metrics = compute_fold_metrics(
            test_trades,
            config.capital_usd,
            fold.test_start,
            fold.test_end,
        )
        daily = daily_equity_series(
            test_trades, config.capital_usd, fold.test_start, fold.test_end
        )

        fold_results.append(
            FoldResult(
                index=fold.index,
                train_start=fold.train_start,
                train_end=fold.train_end,
                test_start=fold.test_start,
                test_end=fold.test_end,
                best_stop_loss_pct=stop_loss,
                best_take_profit_pct=take_profit,
                train_trades=train_trades,
                validation_pnl_usd=validation_pnl.quantize(_MONEY_QUANTUM),
                metrics=metrics,
            )
        )
        fold_metrics.append(metrics)
        fold_returns.append(daily_returns(daily, config.capital_usd))

    aggregate = aggregate_metrics(
        fold_metrics, fold_returns, config.capital_usd
    )

    hold_start = fold_results[0].test_start
    hold_end = fold_results[-1].test_end
    buy_hold: dict[str, Decimal] = {}
    for symbol in sorted(dataset):
        window = candles_in_range(dataset[symbol], hold_start, hold_end)
        if len(window) < 2 or window[0].close == 0:
            buy_hold[symbol] = Decimal("0")
        else:
            gain = window[-1].close / window[0].close - Decimal("1")
            buy_hold[symbol] = (config.capital_usd * gain).quantize(
                _MONEY_QUANTUM
            )

    verdict = "PASA" if aggregate.net_pnl_usd > 0 else "NO PASA"
    return WalkForwardResult(
        config=config,
        folds=tuple(fold_results),
        aggregate=aggregate,
        buy_hold_usd=buy_hold,
        verdict=verdict,
    )


def _fmt(value: Decimal | None) -> str:
    return "n/a" if value is None else str(value)


def render_report(result: WalkForwardResult) -> str:
    """Reporte Markdown en español (RF-5). Determinista: sin timestamps."""
    config = result.config
    lines: list[str] = [
        "# Walk-forward ORB — reporte de evidencia",
        "",
        f"- Símbolos: {', '.join(config.symbols)}",
        f"- Intervalo: {config.interval}",
        f"- Ventanas: train {config.train_days} d / test {config.test_days} d"
        f" / paso {config.step_days} d",
        f"- Costes: comisión {config.fee_rate} por lado,"
        f" slippage {config.slippage_pct} % por lado",
        f"- Capital por ventana: {config.capital_usd} USD",
        "",
        "## Folds",
        "",
        "| # | Train | Test | SL | TP | Trades train | PnL validación"
        " | Trades test | PnL neto | Sharpe | PF | Expectancy |",
        "|---|-------|------|----|----|--------------|-----------------"
        "|------------|----------|--------|----|-------------|",
    ]
    for fold in result.folds:
        metrics = fold.metrics
        note = " *(sin trades en train)*" if fold.train_trades == 0 else ""
        lines.append(
            f"| {fold.index} "
            f"| {fold.train_start} → {fold.train_end} "
            f"| {fold.test_start} → {fold.test_end} "
            f"| {fold.best_stop_loss_pct} | {fold.best_take_profit_pct} "
            f"| {fold.train_trades}{note} "
            f"| {fold.validation_pnl_usd} "
            f"| {metrics.trades} | {metrics.net_pnl_usd} "
            f"| {metrics.sharpe} | {_fmt(metrics.profit_factor)} "
            f"| {metrics.expectancy_usd} |"
        )

    aggregate = result.aggregate
    lines += [
        "",
        "## Agregado out-of-sample",
        "",
        f"- PnL neto total (suma de tests): {aggregate.net_pnl_usd} USD",
        f"- Retorno neto: {aggregate.return_pct} %",
        f"- Máx. drawdown: {aggregate.max_drawdown_usd} USD"
        f" ({aggregate.max_drawdown_pct} %)",
        f"- Sharpe: {aggregate.sharpe}",
        f"- Profit factor: {_fmt(aggregate.profit_factor)}",
        f"- Expectancy: {aggregate.expectancy_usd} USD",
        f"- Trades: {aggregate.trades}"
        f" (ganadores: {aggregate.winning_trades})",
        f"- Comisiones: {aggregate.fees_usd} USD",
        "",
        "## Buy & hold (informativo, no forma parte del gate)",
        "",
    ]
    for symbol, value in sorted(result.buy_hold_usd.items()):
        lines.append(f"- {symbol}: {value} USD sobre 20 USD")
    lines += [
        "",
        "## Veredicto",
        "",
        f"**{result.verdict}**"
        " — gate: PnL neto agregado out-of-sample > 0 tras costes (D-7).",
        "",
    ]
    return "\n".join(lines)
