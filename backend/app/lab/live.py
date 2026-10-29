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
from app.lab.bars import TF_MINUTES, Bar
from app.lab.engine import dec
from app.lab.regime import RegimeLookup
from app.lab import context
from app.lab.strategies import STRATEGIES
from app.signals import alerts
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.risk_guard_service import get_runtime

logger = logging.getLogger(__name__)

HISTORY = 1000  # velas por par y timeframe (máximo de Binance por petición)
LIVE_CAPITAL = Decimal("100")  # una cuenta por estrategia (antes 20/50/100: mismos trades x3)
PRINCIPAL = "principal"  # tu cuenta de 40 USD: copia solo lo que ya ganó en vivo
PRINCIPAL_MAX_OPEN = 3
CHAMPION_MIN_TRADES = 5
CHAMPION_MIN_PF = Decimal("1.3")
STREAK_WINDOW, STREAK_LOSSES, STREAK_PAUSE_MS = 10, 5, 48 * 3_600_000  # video "win rate": 5 de 10 → parar


def champions(trades, benched: set[str]) -> set[str]:
    """Fuentes con ventaja comprobada en LARGOS (Binance Spot no permite cortos).

    Cuenta cada operación una vez (antes había 3 cuentas por estrategia) y exige
    ≥5 cierres, PnL neto > 0 y factor de beneficio ≥ 1.3 ya con comisiones.
    """
    seen, by = set(), {}
    for t in trades:
        key = (t.strategy, t.symbol, t.opened_ts)
        if t.side != "LONG" or t.strategy == PRINCIPAL or key in seen:
            continue
        seen.add(key)
        by.setdefault(t.strategy, []).append(t.pnl)
    out = set()
    for name, pnls in by.items():
        wins = sum((p for p in pnls if p > 0), Decimal(0))
        losses = -sum((p for p in pnls if p < 0), Decimal(0))
        if len(pnls) >= CHAMPION_MIN_TRADES and wins > losses * CHAMPION_MIN_PF and name not in benched:
            out.add(name)
    return out


def _symbols() -> list[str]:
    return [s.strip().upper() for s in settings.lab_symbols.split(",") if s.strip()]


class LabRunner:
    def __init__(self, session_factory=None, market=None) -> None:
        self.session_factory = session_factory or database.SessionLocal
        self.market = market or BinanceMarketDataClient()
        self.symbols = _symbols()
        self.strategies = list(STRATEGIES)
        self.benched: set[str] = set()  # el cerebro las mandó a la banca: no abren más
        self.champions: set[str] = set()  # las únicas que copia la cuenta principal
        self.streak: dict[str, list[bool]] = {}  # últimos resultados por estrategia (True = ganó)
        self.paused_until: dict[str, int] = {}  # pausa de 48 h tras perder 5 de 10 (research: mejora ambas mitades)
        self.principal_capital = Decimal(str(settings.configured_capital_usd))
        self.timeframes = sorted(TF_MINUTES, key=TF_MINUTES.get)
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
            self.accounts = store.load_accounts(db, [s.name for s in STRATEGIES], (LIVE_CAPITAL,))
            for strategy in STRATEGIES:
                if strategy.fee_rate is not None and (strategy.name, LIVE_CAPITAL) in self.accounts:
                    self.accounts[(strategy.name, LIVE_CAPITAL)].fee_rate = strategy.fee_rate
            self.accounts.update(store.load_accounts(db, [PRINCIPAL], (self.principal_capital,)))
        self.sync_brain()

    def sync_brain(self) -> None:
        """Toma del cerebro las estrategias aprobadas y la banca (se llama tras cada ciclo)."""
        from app.brain.evolve import EVOLVED_CAPITAL, live_strategies

        with self.session_factory() as db:
            evolved, self.benched = live_strategies(db)
            if evolved:
                self.accounts.update(store.load_accounts(db, [s.name for s in evolved], (Decimal(EVOLVED_CAPITAL),)))
            trades = store.closed_trades(db)
            self.champions = champions(trades, self.benched)
        if not self.streak:  # al arrancar: reconstruye rachas y pausas con el historial
            seen = set()
            for t in sorted(trades, key=lambda t: t.closed_ts or 0):
                if (t.strategy, t.symbol, t.opened_ts) not in seen:
                    seen.add((t.strategy, t.symbol, t.opened_ts))
                    self._record(t.strategy, t.pnl > 0, t.closed_ts or 0)
        telegram = [s for s in self.strategies if s.name.startswith("tg_")]
        self.strategies = list(STRATEGIES) + evolved + telegram

    def _record(self, name: str, won: bool, ts: int) -> None:
        last = (self.streak.get(name, []) + [won])[-STREAK_WINDOW:]
        if len(last) == STREAK_WINDOW and last.count(False) >= STREAK_LOSSES:
            self.paused_until[name], last = ts + STREAK_PAUSE_MS, []
        self.streak[name] = last

    def paused(self, name: str, now_ms: int) -> bool:
        return self.paused_until.get(name, 0) > now_ms

    def btc_ok(self) -> bool:
        """Mercado a favor: BTC diario cerró sobre su SMA20 (sin datos → no)."""
        closes = [b.c for b in self.bars.get(("BTCUSDT", "1d"), [])[-20:]]
        return len(closes) == 20 and closes[-1] > sum(closes) / 20

    @property
    def principal(self):
        return self.accounts.get((PRINCIPAL, self.principal_capital))

    def mirror(self, source: str, symbol: str, side: str, stop, take_profit, ts: int):
        """La cuenta principal entra solo si la fuente está comprobada (y en largo)."""
        account = self.principal
        if (account is None or side != "LONG" or source not in self.champions
                or f"{source}|{symbol}" in self.benched or symbol in account.positions
                or len(account.positions) >= PRINCIPAL_MAX_OPEN or symbol not in self.prices
                or not self.btc_ok()  # con BTC bajo su SMA20 la cuenta principal no compra
                or context.macro_blackout()):  # ni 12 h antes / 6 h después de FOMC o CPI
            return None
        opened = account.open(symbol=symbol, side=side, price=self.prices[symbol], stop=stop,
                              take_profit=take_profit, ts=ts, regime=source[:40], prices=self.prices)
        if opened:
            with self.session_factory() as db:
                store.save_open(db, account, opened)
            alerts.on_open(type("P", (), {"name": PRINCIPAL})(), symbol, opened)
        return opened

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

    def close_orphans(self) -> int:
        """Posiciones abiertas de estrategias que ya no están en el torneo: se cierran al precio actual.

        Sin esto quedaban "abiertas" para siempre en el panel (nadie las vigilaba).
        """
        from sqlalchemy import select

        from app.lab.engine import FEE_RATE
        from app.lab.models import LabTrade

        closed = 0
        with self.session_factory() as db:
            for row in db.scalars(select(LabTrade).where(LabTrade.status == "OPEN")):
                key = (row.strategy, Decimal(row.capital).normalize())
                if any((n, c.normalize()) == key for n, c in self.accounts) or row.symbol not in self.prices:
                    continue
                price, qty = self.prices[row.symbol], Decimal(row.qty)
                gross = qty * price if row.side == "LONG" else Decimal(row.notional) + qty * (Decimal(row.entry) - price)
                fee = qty * price * FEE_RATE
                row.status, row.exit_price, row.reason = "CLOSED", price, "retirada"
                row.closed_ts = int(time.time() * 1000)
                row.pnl = gross - fee - Decimal(row.notional) - Decimal(row.entry_fee)
                row.fees = Decimal(row.entry_fee) + fee
                closed += 1
            db.commit()
        if closed:
            logger.info("lab: %s orphan positions of retired strategies closed", closed)
        return closed

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
        for strategy in self.strategies:
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
                allowed = getattr(strategy, "symbols", None)
                regime = getattr(strategy, "regime_filter", False)
                if signal is not None and ((regime is True and not self.btc_ok()) or (regime == "bear" and self.btc_ok())):
                    continue
                if signal is not None and self.paused(strategy.name, close_ts):
                    continue
                if (signal is None or not running or strategy.name in self.benched
                        or f"{strategy.name}|{symbol}" in self.benched or (allowed and symbol not in allowed)):
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
                    self.mirror(strategy.name, symbol, signal.side, opened.stop, opened.take_profit, close_ts)

    def _close(self, account, symbol: str, price: Decimal, reason: str) -> None:
        db_id = account.positions[symbol].db_id
        trade = account.close(symbol, price, int(time.time() * 1000), reason)
        with self.session_factory() as db:
            store.save_close(db, account, db_id, trade)
        alerts.on_close(account.strategy, "Cuenta principal", symbol, trade)
        if trade is not None:
            self._record(account.strategy, trade.pnl > 0, trade.closed_ts)
        mirrored = self.principal.positions.get(symbol) if self.principal and account.strategy != PRINCIPAL else None
        if mirrored is not None and mirrored.regime == account.strategy[:40]:
            self._close(self.principal, symbol, price, reason)

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
                await asyncio.to_thread(self.close_orphans)
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
            "strategies": len(self.strategies),
            "benched": sorted(self.benched),
            "champions": sorted(self.champions),
            "macro": {"bloqueo": context.macro_blackout(), "proximo": context.next_event()},
            "contexto": context.latest,
            "btc_ok": self.btc_ok(),
            "waiting": {
                s.name: "espera a que BTC cierre sobre su SMA20 diaria"
                for s in self.strategies if getattr(s, "regime_filter", False) is True and not self.btc_ok()
            } | {
                s.name: "corto: espera a que BTC cierre bajo su SMA20 diaria"
                for s in self.strategies if getattr(s, "regime_filter", False) == "bear" and self.btc_ok()
            } | {
                name: "pausa de 48 h: perdió 5 de sus últimas 10"
                for name, until in self.paused_until.items()
                if until > time.time() * 1000 and name in {s.name for s in self.strategies}
            },
            "regimes": {
                s: r.labels[-1] if r.labels else "sin datos" for s, r in self.regimes.items()
            },
        }


runner: LabRunner | None = None
