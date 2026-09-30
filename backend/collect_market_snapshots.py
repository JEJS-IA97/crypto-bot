from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from app.config import settings
from app.services.exchange_market_service import fetch_exchange_quotes


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect public cross-exchange quote snapshots.")
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=3600.0)
    parser.add_argument("--output", default="data/market_snapshots.jsonl")
    args = parser.parse_args()

    symbols = [s.upper() for s in (args.symbols or settings.simulation_bot_symbols.split(",")) if s.strip()]
    start = time.monotonic()

    with open(args.output, "a", encoding="utf-8") as handle:
        while time.monotonic() - start < args.duration:
            cycle_started = time.monotonic()
            timestamp = datetime.now(timezone.utc).isoformat()

            for symbol in symbols:
                quotes = fetch_exchange_quotes(symbol)
                payload = {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "quotes": quotes,
                }
                handle.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")
                handle.flush()
                print(f"{timestamp} {symbol} snapshots={len(quotes)}")

            sleep_for = max(0.0, args.interval - (time.monotonic() - cycle_started))
            time.sleep(sleep_for)


if __name__ == "__main__":
    main()
