from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.signal_engine import Candle, StrategyConfig as SignalConfig
from app.services.strategy_lab_service import (
    KlineBacktestConfig,
    OrbBacktestConfig,
    backtest_candles,
    backtest_orb,
    final_parameters_section,
    load_klines_jsonl,
    split_candles,
    write_final_parameters,
)


def load_klines_dir(klines_dir: str | Path) -> dict[str, list[Candle]]:
    directory = Path(klines_dir)
    files = sorted(directory.glob("*.jsonl"))
    if not files:
        raise SystemExit(f"No kline JSONL files found in {directory}")
    return {path.stem: load_klines_jsonl(path) for path in files}


def build_signal_configs() -> list[SignalConfig]:
    configs: list[SignalConfig] = []
    for ema_short in (10, 20, 30):
        for rsi_buy_max in ("65", "70", "75"):
            for volume_factor in ("1.2", "1.5"):
                configs.append(
                    SignalConfig(
                        ema_short_period=ema_short,
                        rsi_buy_max=Decimal(rsi_buy_max),
                        volume_factor=Decimal(volume_factor),
                    )
                )
    return configs


_MONEY_QUANTUM = Decimal("0.00000001")
_PCT_QUANTUM = Decimal("0.01")


def _split_all(
    per_symbol: dict[str, list[Candle]],
) -> tuple[
    dict[str, list[Candle]],
    dict[str, list[Candle]],
    dict[str, list[Candle]],
]:
    train: dict[str, list[Candle]] = {}
    validation: dict[str, list[Candle]] = {}
    test: dict[str, list[Candle]] = {}
    for symbol, candles in per_symbol.items():
        train[symbol], validation[symbol], test[symbol] = split_candles(candles)
    return train, validation, test


def _aggregate(
    strategy: SignalConfig,
    per_symbol: dict[str, list[Candle]],
    kline_config: KlineBacktestConfig,
) -> dict[str, Any]:
    results = [
        backtest_candles(candles, strategy, kline_config)
        for candles in per_symbol.values()
        if candles
    ]
    return _aggregate_results(results, kline_config.capital_usd)


def _aggregate_orb(
    per_symbol: dict[str, list[Candle]],
    orb_config: OrbBacktestConfig,
) -> dict[str, Any]:
    results = [
        backtest_orb(candles, orb_config)
        for candles in per_symbol.values()
        if candles
    ]
    return _aggregate_results(results, orb_config.capital_usd)


def _aggregate_results(
    results: list[Any],
    capital: Decimal,
) -> dict[str, Any]:
    if not results:
        return {
            "net_pnl_usd": Decimal("0"),
            "trades": 0,
            "winning_trades": 0,
            "fees_usd": Decimal("0"),
            "return_pct": Decimal("0"),
            "max_drawdown_pct": Decimal("0"),
            "win_rate_pct": Decimal("0"),
            "candles": 0,
            "results": [],
        }

    net = sum((result.net_pnl_usd for result in results), Decimal("0"))
    trades = sum(result.trades for result in results)
    winning = sum(result.winning_trades for result in results)
    fees = sum((result.fees_usd for result in results), Decimal("0"))
    total_capital = capital * Decimal(str(len(results)))
    return {
        "net_pnl_usd": net.quantize(_MONEY_QUANTUM),
        "trades": trades,
        "winning_trades": winning,
        "fees_usd": fees.quantize(_MONEY_QUANTUM),
        "return_pct": (net * Decimal("100") / total_capital).quantize(
            _PCT_QUANTUM
        ),
        "max_drawdown_pct": max(
            (result.max_drawdown_pct for result in results),
            default=Decimal("0"),
        ).quantize(_PCT_QUANTUM),
        "win_rate_pct": (
            Decimal(str(winning)) / Decimal(str(trades)) * Decimal("100")
            if trades
            else Decimal("0")
        ).quantize(_PCT_QUANTUM),
        "candles": sum(result.candles for result in results),
        "results": results,
    }


def _fmt(value: Any) -> str:
    if isinstance(value, Decimal):
        return f"{value:f}"
    return str(value)


def _print_ranking(
    ranked: list[tuple[SignalConfig, dict[str, Any]]],
) -> None:
    print("\nGRID (TRAIN)")
    for position, (config, aggregate) in enumerate(ranked, start=1):
        print(
            f"  {position:2d}. ema={config.ema_short_period:<3}"
            f" rsi_buy_max={config.rsi_buy_max:<5}"
            f" volume_factor={config.volume_factor:<5}"
            f" -> net {_fmt(aggregate['net_pnl_usd'])} USD"
            f" | {aggregate['trades']} ops"
            f" | dd {_fmt(aggregate['max_drawdown_pct'])}%"
        )


def _print_metrics(label: str, aggregate: dict[str, Any]) -> None:
    print(f"\n{label}")
    print(f"  Velas:        {aggregate['candles']}")
    print(f"  Operaciones:  {aggregate['trades']}")
    print(f"  Ganadoras:    {aggregate['winning_trades']}")
    print(f"  Win rate:     {_fmt(aggregate['win_rate_pct'])}%")
    print(f"  Comisiones:   {_fmt(aggregate['fees_usd'])} USD")
    print(f"  PnL neto:     {_fmt(aggregate['net_pnl_usd'])} USD")
    print(f"  Rentabilidad: {_fmt(aggregate['return_pct'])}%")
    print(f"  Drawdown:     {_fmt(aggregate['max_drawdown_pct'])}%")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Grid search de la estrategia de señales y backtest ORB sobre"
            " klines históricos (RF-15)."
        )
    )
    parser.add_argument(
        "--klines-dir",
        default="data/klines",
        help="Directorio con los ficheros *.jsonl del recolector T14",
    )
    parser.add_argument(
        "--klines-orb-dir",
        default="data/klines5m",
        help=(
            "Directorio con los ficheros *.jsonl de 5m para el backtest ORB"
            " (collect_klines.py --interval 5m)"
        ),
    )
    parser.add_argument(
        "--strategy",
        choices=("both", "signal", "orb"),
        default="both",
        help="Qué evaluar: EMA/RSI, ORB o ambas (defecto: both)",
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="Ruta del plan.md donde escribir 'Parámetros finales'",
    )
    parser.add_argument(
        "--slippage",
        default="0.05",
        help="Slippage configurable en %% por lado (defecto 0.05)",
    )
    parser.add_argument(
        "--capital",
        default="20",
        help="Capital en USD por backtest (defecto 20)",
    )
    parser.add_argument(
        "--no-write-plan",
        action="store_true",
        help="No tocar el plan: sólo imprimir la sección",
    )
    args = parser.parse_args()

    run_signal = args.strategy in ("both", "signal")
    run_orb = args.strategy in ("both", "orb")

    kline_config = KlineBacktestConfig(
        slippage_pct=Decimal(args.slippage),
        capital_usd=Decimal(args.capital),
    )

    signal_splits: dict[str, dict[str, Any]] = {}
    orb_splits: dict[str, dict[str, Any]] = {}
    best: SignalConfig | None = None
    metrics: dict[str, Any] | None = None
    notes: list[str] = []

    if run_signal:
        per_symbol = load_klines_dir(args.klines_dir)
        train, validation, test = _split_all(per_symbol)

        print(f"Símbolos: {len(per_symbol)}")
        print(
            f"Train: {sum(len(c) for c in train.values())} velas"
            f" | Validation: {sum(len(c) for c in validation.values())} velas"
            f" | Test: {sum(len(c) for c in test.values())} velas"
        )

        ranked: list[tuple[SignalConfig, dict[str, Any]]] = sorted(
            (
                (config, _aggregate(config, train, kline_config))
                for config in build_signal_configs()
            ),
            key=lambda item: (
                item[1]["net_pnl_usd"],
                item[1]["win_rate_pct"],
                -item[1]["max_drawdown_pct"],
            ),
            reverse=True,
        )
        if not ranked or ranked[0][1]["trades"] == 0:
            raise SystemExit(
                "No strategy produced trades on the train split."
            )

        _print_ranking(ranked)
        best, train_metrics = ranked[0]

        # El mejor se evalúa en validación y test SIN re-seleccionar.
        valid_metrics = _aggregate(best, validation, kline_config)
        test_metrics = _aggregate(best, test, kline_config)
        _print_metrics("MEJOR CONFIGURACIÓN — TRAIN", train_metrics)
        _print_metrics("MEJOR CONFIGURACIÓN — VALIDATION", valid_metrics)
        _print_metrics("MEJOR CONFIGURACIÓN — TEST", test_metrics)

        signal_splits = {
            "TRAIN": train_metrics,
            "VALIDATION": valid_metrics,
            "TEST": test_metrics,
        }
        metrics = {
            "Rentabilidad neta (TRAIN)": (
                f"{_fmt(train_metrics['net_pnl_usd'])} USD"
            ),
            "Rentabilidad % (TRAIN)": (
                f"{_fmt(train_metrics['return_pct'])}%"
            ),
            "Drawdown máximo (TRAIN)": (
                f"{_fmt(train_metrics['max_drawdown_pct'])}%"
            ),
            "Operaciones (TRAIN)": train_metrics["trades"],
            "Win rate (TRAIN)": (
                f"{_fmt(train_metrics['win_rate_pct'])}%"
            ),
            "Rentabilidad neta (VALIDATION)": (
                f"{_fmt(valid_metrics['net_pnl_usd'])} USD"
            ),
            "Rentabilidad neta (TEST)": (
                f"{_fmt(test_metrics['net_pnl_usd'])} USD"
            ),
            "Split": "train 70% / validation 15% / test 15% (cronológico)",
        }
        notes = [
            "Selección de hiperparámetros únicamente sobre TRAIN.",
            (
                "VALIDATION y TEST sin re-selección para estimar"
                " la generalización (sin look-ahead)."
            ),
            (
                "Costes modelados: comisión 0.1% por lado y slippage"
                f" {_fmt(kline_config.slippage_pct)}% por lado."
            ),
        ]

    if run_orb:
        directory = Path(args.klines_orb_dir)
        files = sorted(directory.glob("*.jsonl")) if directory.is_dir() else []
        if not files:
            if args.strategy == "orb":
                raise SystemExit(
                    f"No 5m kline JSONL files found in {directory}"
                    " (collect them with collect_klines.py --interval 5m)."
                )
            print(
                f"\nORB: sin datos 5m en {directory} — comparación"
                " omitida (collect_klines.py --interval 5m)."
            )
        else:
            per_symbol_5m = load_klines_dir(directory)
            orb_train, orb_validation, orb_test = _split_all(per_symbol_5m)
            if not run_signal:
                print(f"Símbolos: {len(per_symbol_5m)}")
            print(
                f"\nORB (5m):"
                f" {sum(len(c) for c in per_symbol_5m.values())} velas"
                f" | Train: {sum(len(c) for c in orb_train.values())}"
                f" | Validation: {sum(len(c) for c in orb_validation.values())}"
                f" | Test: {sum(len(c) for c in orb_test.values())}"
            )
            orb_config = OrbBacktestConfig(
                slippage_pct=kline_config.slippage_pct,
                capital_usd=kline_config.capital_usd,
            )
            orb_splits = {
                "TRAIN": _aggregate_orb(orb_train, orb_config),
                "VALIDATION": _aggregate_orb(orb_validation, orb_config),
                "TEST": _aggregate_orb(orb_test, orb_config),
            }
            for label in ("TRAIN", "VALIDATION", "TEST"):
                _print_metrics(f"ORB — {label}", orb_splits[label])

    if orb_splits and signal_splits:
        print("\nCOMPARATIVA ORB vs EMA/RSI (PnL neto | operaciones)")
        for label in ("TRAIN", "VALIDATION", "TEST"):
            orb_metrics = orb_splits[label]
            signal_metrics = signal_splits[label]
            print(
                f"  {label:<10} ORB {_fmt(orb_metrics['net_pnl_usd'])} USD"
                f" ({orb_metrics['trades']} ops) |"
                f" EMA/RSI {_fmt(signal_metrics['net_pnl_usd'])} USD"
                f" ({signal_metrics['trades']} ops)"
            )

    if not run_signal:
        return

    plan_path = args.plan
    if plan_path is None:
        plan_path = (
            Path(__file__).resolve().parent.parent
            / "specs"
            / "001-bot-binance-spot"
            / "plan.md"
        )

    if args.no_write_plan:
        print()
        print(
            final_parameters_section(
                strategy=best,
                kline_config=kline_config,
                metrics=metrics,
                notes=notes,
            )
        )
        return

    write_final_parameters(
        plan_path,
        strategy=best,
        kline_config=kline_config,
        metrics=metrics,
        notes=notes,
    )
    print(f"\nParámetros finales escritos en: {plan_path}")


if __name__ == "__main__":
    main()
