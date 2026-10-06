"""Recolector de klines históricos de Binance (spec 001, RF-15 soporte).

Descarga `/api/v3/klines` (público, **sin credenciales**) en bloques de
1000 velas para los 8 pares configurados y escribe un JSONL por par en
`data/klines/<SYMBOL>.jsonl`. Es reanudable: si el fichero ya existe,
continúa desde la última vela escrita, sin duplicar filas; lo ya
descargado se conserva aunque la red se corte a mitad.

Los importes se guardan como texto (Decimal desde string, sin float).

Uso:
    python collect_klines.py [--symbols BTCUSDT,...] [--days 365]
                             [--start-time MS] [--interval 15m]
                             [--data-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

DEFAULT_BASE_URL = "https://api.binance.com"
DEFAULT_INTERVAL = "15m"
DEFAULT_DAYS = 365
CHUNK_SIZE = 1000

_INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data" / "klines"


class CollectionError(RuntimeError):
    """Fallo de red o de formato: se detiene y se reanuda en la siguiente."""


def interval_to_ms(interval: str) -> int:
    try:
        return _INTERVAL_MS[interval]
    except KeyError:
        raise ValueError(f"intervalo no soportado: {interval}") from None


def klines_file(data_dir: str | Path, symbol: str) -> Path:
    return Path(data_dir) / f"{symbol.upper()}.jsonl"


def load_last_open_time(path: Path) -> int | None:
    """Última `open_time` del JSONL; None si no existe o está vacío."""
    if not path.exists():
        return None
    last: int | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                last = int(json.loads(raw)["open_time"])
            except (KeyError, TypeError, ValueError):
                # Línea corrupta: se ignora y se reanuda tras la última buena.
                continue
    return last


def _candle_line(row: list[Any]) -> str:
    open_time = int(row[0])
    payload = {
        "open_time": open_time,
        "open": str(row[1]),
        "high": str(row[2]),
        "low": str(row[3]),
        "close": str(row[4]),
        "volume": str(row[5]),
        "close_time": int(row[6]),
        "quote_volume": str(row[7]),
        "trades": int(row[8]),
    }
    return json.dumps(payload, separators=(",", ":"))


def fetch_chunk(
    symbol: str,
    *,
    interval: str,
    start_time: int,
    limit: int = CHUNK_SIZE,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 30.0,
) -> list[list[Any]]:
    """Un bloque de `/api/v3/klines` empezando en `start_time` (incluido)."""
    url = f"{base_url.rstrip('/')}/api/v3/klines"
    try:
        response = httpx.request(
            method="GET",
            url=url,
            params={
                "symbol": symbol.upper(),
                "interval": interval,
                "startTime": int(start_time),
                "limit": limit,
            },
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise CollectionError(
            f"sin respuesta de Binance para {symbol}: {exc}"
        ) from exc
    if response.is_error:
        raise CollectionError(
            f"Binance respondió {response.status_code} para {symbol}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise CollectionError(
            f"Binance devolvió JSON inválido para {symbol}"
        ) from exc
    if not isinstance(payload, list):
        raise CollectionError(
            f"payload inesperado de klines para {symbol}"
        )
    return payload


def download_symbol(
    symbol: str,
    *,
    data_dir: str | Path,
    interval: str = DEFAULT_INTERVAL,
    start_time: int | None = None,
    days: int = DEFAULT_DAYS,
    limit: int = CHUNK_SIZE,
    base_url: str = DEFAULT_BASE_URL,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Descarga el histórico de un par en bloques; reanudable.

    Orden de inicio: si ya hay datos, la vela siguiente a la última;
    si no, `start_time`; si no, `ahora - days` días.
    """
    step = interval_to_ms(interval)
    path = klines_file(data_dir, symbol)
    previous_last = load_last_open_time(path)
    if previous_last is not None:
        next_start = previous_last + step
    elif start_time is not None:
        next_start = int(start_time)
    else:
        current = (
            int(time.time() * 1000) if now_ms is None else int(now_ms)
        )
        next_start = current - days * 86_400_000

    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    requests_count = 0
    last_written = previous_last

    with path.open("a", encoding="utf-8") as handle:
        while True:
            rows = fetch_chunk(
                symbol,
                interval=interval,
                start_time=next_start,
                limit=limit,
                base_url=base_url,
            )
            requests_count += 1
            if not rows:
                break

            new_in_chunk = 0
            for row in rows:
                open_ms = int(row[0])
                if last_written is not None and open_ms <= last_written:
                    # Nunca duplicar velas ya escritas (defensa extra).
                    continue
                handle.write(_candle_line(row) + "\n")
                written += 1
                new_in_chunk += 1
                last_written = open_ms
            handle.flush()

            if new_in_chunk == 0:
                # La API no avanzó: cortamos para no repetir en bucle.
                break
            next_start = int(rows[-1][0]) + step
            if len(rows) < limit:
                # Bloque corto = no hay más historial hacia delante.
                break

    return {
        "symbol": symbol.upper(),
        "path": str(path),
        "written": written,
        "requests": requests_count,
        "last_open_time": last_written,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Descarga klines históricos de Binance a data/klines/*.jsonl "
            "(reanudable, sin credenciales)."
        )
    )
    parser.add_argument(
        "--symbols",
        default=settings.trading_symbols,
        help="lista de pares separados por comas (defecto: los 8 del bot)",
    )
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument(
        "--start-time",
        type=int,
        default=None,
        help="openTime inicial en ms (solo si el fichero está vacío)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(_DEFAULT_DATA_DIR),
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbols = [
        part.strip().upper()
        for part in args.symbols.split(",")
        if part.strip()
    ]
    if not symbols:
        print("sin símbolos que descargar", file=sys.stderr)
        return 2

    failed = False
    for symbol in symbols:
        try:
            stats = download_symbol(
                symbol,
                data_dir=args.data_dir,
                interval=args.interval,
                start_time=args.start_time,
                days=args.days,
                base_url=args.base_url,
            )
        except (CollectionError, ValueError) as exc:
            failed = True
            print(f"{symbol}: error — {exc}", file=sys.stderr)
            continue
        print(
            f"{symbol}: {stats['written']} velas nuevas "
            f"({stats['requests']} peticiones) → {stats['path']}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
