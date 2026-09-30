from __future__ import annotations

import argparse
from decimal import Decimal

from app.services.strategy_lab_service import (
    StrategyConfig,
    grid_search,
    load_jsonl,
    result_to_json,
    split_time_series,
)


def build_configs() -> list[StrategyConfig]:
    configs: list[StrategyConfig] = []
    for min_profit_percent in ("0.10", "0.15", "0.20", "0.25", "0.30"):
        for latency in (1, 2, 3, 5):
            for slippage in ("0.05", "0.08", "0.12"):
                configs.append(
                    StrategyConfig(
                        capital_usd=Decimal("5"),
                        min_profit_usd=Decimal("0.05"),
                        min_profit_percent=Decimal(min_profit_percent),
                        taker_slippage_percent=Decimal(slippage),
                        assumed_latency_seconds=latency,
                        cooldown_seconds=60,
                    )
                )
    return configs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Time-series strategy optimizer for cross-exchange arbitrage snapshots."
    )
    parser.add_argument("input", help="JSONL snapshot file")
    args = parser.parse_args()

    snapshots = load_jsonl(args.input)
    train, validation, test = split_time_series(snapshots)

    print(f"Snapshots: {len(snapshots)}")
    print(f"Train: {len(train)} | Validation: {len(validation)} | Test: {len(test)}")

    ranked = grid_search(train, build_configs())
    if not ranked:
        raise SystemExit("No strategy configurations were evaluated.")

    candidate = ranked[0]
    print("\nTRAIN CANDIDATE")
    print(result_to_json(candidate))

    print("\nVALIDATION")
    print(result_to_json(ranked[0] if not validation else __import__("app.services.strategy_lab_service", fromlist=["backtest"]).backtest(validation, candidate.config)))

    print("\nTEST")
    print(result_to_json(ranked[0] if not test else __import__("app.services.strategy_lab_service", fromlist=["backtest"]).backtest(test, candidate.config)))


if __name__ == "__main__":
    main()
