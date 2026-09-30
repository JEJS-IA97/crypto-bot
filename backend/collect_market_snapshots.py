from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.services.exchange_market_service import fetch_exchange_quotes


def collect_snapshot(
    symbol: str,
    timestamp: str,
) -> dict:
    quotes = fetch_exchange_quotes(symbol)
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "quotes": quotes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect public cross-exchange quote snapshots."
    )
    parser.add_argument(
        "--symbol",
        action="append",
        dest="symbols",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3600.0,
    )
    parser.add_argument(
        "--output",
        default="data/market_snapshots.jsonl",
    )
    args = parser.parse_args()

    symbols = [
        symbol.strip().upper()
        for symbol in (
            args.symbols
            or settings.simulation_bot_symbols.split(",")
        )
        if symbol.strip()
    ]

    if not symbols:
        raise SystemExit("No symbols configured.")

    output_path = Path(args.output)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    start = time.monotonic()

    with output_path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        while time.monotonic() - start < args.duration:
            cycle_started = time.monotonic()
            timestamp = datetime.now(
                timezone.utc
            ).isoformat()

            for symbol in symbols:
                payload = collect_snapshot(
                    symbol=symbol,
                    timestamp=timestamp,
                )

                handle.write(
                    json.dumps(
                        payload,
                        default=str,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                handle.flush()

                print(
                    f"{timestamp} "
                    f"{symbol} "
                    f"snapshots="
                    f"{len(payload['quotes'])}"
                )

            sleep_for = max(
                0.0,
                args.interval
                - (
                    time.monotonic()
                    - cycle_started
                ),
            )
            time.sleep(sleep_for)


if __name__ == "__main__":
    main()