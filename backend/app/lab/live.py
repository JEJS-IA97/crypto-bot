"""Torneo en vivo: WebSocket de Binance → 30 cuentas virtuales operando a la vez.

- `@miniTicker` (cada ~1 s): precio actual de cada par → revisa stop y
  take-profit de todas las posiciones abiertas.
- `@kline_<tf>` cerrada: añade la vela, recalcula la señal de las estrategias
  de ese timeframe y abre/cierra posiciones. Velas de 1h → régimen.
Al arrancar recupera cuentas y posiciones de la BD y siembra el historial por
REST. Reconecta solo (backoff hasta 60 s). Respeta el kill switch del bot.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import timezone
from decimal import Decimal

import websockets

from app import database
from app.config import settings
from app.lab import store
from app.lab.backtest import CAPITALS
from app.lab.bars import TF_MINUTES, Bar
from app.lab.engine import dec
from app.lab.regime import RegimeLookup
from app.lab.strategies import STRATEGIES
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.risk_guard_service import get_runtime

logger = logging.getLogger(__name__)

HISTORY = 1000  # velas por par y timeframe (máximo de Binance por petición)


def _symbols() -> list[str]:
    return [s.strip().upper() for s in settings.lab_symbols.split(",") if s.strip()]


class LabRunner:
    def __init__(self, session_factory=None, market=None) -> None:
        self.session_factory = session_factory or database.SessionLocal
        self.market = market or BinanceMarketDataClient()
        self.symbols = _symbols()
        self.timeframes = sorted({s.timeframe for s in STRATEGIES}, key=TF_MINUTES.get)
        self.bars: dict[tuple[str, str], list[Bar]] = {}
        self.regimes: dict[str, RegimeLookup] = {}
        self.prices: dict[str, Decimal] = {}
        self.accounts = {}
        self.connected = False
        self.last_tick: float | None = None
        self.ticks = 0
        self.started_at = time.time()

    # --- arranque -----------------------------------------------------
    def restore(self) -> None:
        with self.session_factory() as db:
            self.accounts = store.load_accounts(db, [s.name for s in STRATEGIES], CAPITALS)

    def seed(self) -> None:
        now_ms = int(time.time() * 1000)
        for symbol in self.symbols:
            for tf in self.timeframes:
                candles = self.market.get_klines(symbol, interval=tf, limit=HISTORY)
                tf_ms = TF_MINUTES[tf] * 60_000
                bars = [
                    Bar(
                        int(c.open_time.replace(tzinfo=timezone.utc).timestamp() * 1000),
                        float(c.open), float(c.high), float(c.low), float(c.close), float(c.volume),
                    )
                    for c in candles
                ]
                self.bars[(symbol, tf)] = [b for b in bars if b.ts + tf_ms <= now_ms]
            hourly = self.bars.get((symbol, "1h"), [])
            self.regimes[symbol] = RegimeLookup(hourly)
            if hourly:
                self.prices[symbol] = dec(hourly[-1].c)

    def stream_url(self) -> str:
        streams = []
        for symbol in self.symbols:
            low = symbol.lower()
            streams.append(f"{low}@miniTicker")
            streams += [f"{low}@kline_{tf}" for tf in self.timeframes]
        return f"{settings.lab_ws_url}?streams={'/'.join(streams)}"

    # --- eventos ------------------------------------------------------
    def handle(self, message: dict) -> None:
        data = message.get("data", message)
        event = data.get("e")
        if event == "24hrMiniTicker":
            self.on_price(data["s"], dec(data["c"]))
        elif event == "kline" and data["k"]["x"]:
            k = data["k"]
            bar = Bar(int(k["t"]), float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k["v"]))
            self.on_bar_closed(data["s"], k["i"], bar)

    def on_price(self, symbol: str, price: Decimal) -> None:
        self.prices[symbol] = price
        self.last_tick = time.time()
        self.ticks += 1
        for account in self.accounts.values():
            position = account.positions.get(symbol)
            if position is None:
                continue
            hit = position.hit(price, price)
            if hit:
                self._close(account, symbol, hit[1], hit[0])

    def on_bar_closed(self, symbol: str, tf: str, bar: Bar) -> None:
        key = (symbol, tf)
        series = self.bars.setdefault(key, [])
        if series and series[-1].ts >= bar.ts:
            return
        series.append(bar)
        del series[:-HISTORY]
        if tf == "1h":
            self.regimes[symbol] = RegimeLookup(series)
        tf_ms = TF_MINUTES[tf] * 60_000
        close_ts = bar.ts + tf_ms
        price = self.prices.get(symbol, dec(bar.c))
        running = self._running()
        for strategy in STRATEGIES:
            if strategy.timeframe != tf:
                continue
            signal = strategy.signals(series)[-1] if len(series) >= 2 else None
            for (name, _capital), account in self.accounts.items():
                if name != strategy.name:
                    continue
                position = account.positions.get(symbol)
                if position is not None:
                    held = (close_ts - position.opened_ts) // tf_ms
                    if strategy.max_hold and held >= strategy.max_hold:
                        self._close(account, symbol, price, "tiempo")
                    elif strategy.exit_now(series, len(series) - 1, position.side):
                        self._close(account, symbol, price, "salida")
                    continue
                if signal is None or not running:
                    continue
                opened = account.open(
                    symbol=symbol,
                    side=signal.side,
                    price=price,
                    stop=dec(signal.stop) if signal.stop is not None else None,
                    take_profit=dec(signal.take_profit) if signal.take_profit is not None else None,
                    ts=close_ts,
                    regime=self.regimes[symbol].at(close_ts) if symbol in self.regimes else "sin datos",
                    prices=self.prices,
                )
                if opened:
                    with self.session_factory() as db:
                        store.save_open(db, account, opened)

    def _close(self, account, symbol: str, price: Decimal, reason: str) -> None:
        db_id = account.positions[symbol].db_id
        trade = account.close(symbol, price, int(time.time() * 1000), reason)
        with self.session_factory() as db:
            store.save_close(db, account, db_id, trade)

    def _running(self) -> bool:
        try:
            with self.session_factory() as db:
                return bool(get_runtime(db).running)
        except Exception:
            logger.exception("lab: could not read kill switch")
            return False

    # --- bucle --------------------------------------------------------
    async def run(self, stop_event: asyncio.Event) -> None:
        await asyncio.to_thread(self.restore)
        delay = 1
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self.seed)
                async with websockets.connect(self.stream_url(), ping_interval=20) as ws:
                    self.connected, delay = True, 1
                    logger.info("lab: websocket connected (%s symbols)", len(self.symbols))
                    while not stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except TimeoutError:
                            continue
                        try:
                            self.handle(json.loads(raw))
                        except Exception:
                            logger.exception("lab: could not process message")
            except Exception as exc:
                logger.warning("lab: feed down (%s), retrying in %ss", exc, delay)
            finally:
                self.connected = False
            if not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
                except TimeoutError:
                    pass
                delay = min(delay * 2, 60)

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "symbols": self.symbols,
            "ticks": self.ticks,
            "seconds_since_tick": round(time.time() - self.last_tick, 1) if self.last_tick else None,
            "prices": {s: float(p) for s, p in self.prices.items()},
            "regimes": {
                s: r.labels[-1] if r.labels else "sin datos" for s, r in self.regimes.items()
            },
        }


runner: LabRunner | None = None
