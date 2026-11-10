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
from collections import deque
import logging
import time
from datetime import timezone
from decimal import Decimal
from pathlib import Path

import websockets

from app import database
from app.config import settings
from app.lab import store
from app.lab.bars import TF_MINUTES, Bar
from app.lab.engine import dec
from app.lab.regime import RegimeLookup
from app.lab import context, real
from app.lab.strategies import STRATEGIES
from app.signals import alerts
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.risk_guard_service import get_runtime

logger = logging.getLogger(__name__)

HISTORY = 1000  # velas por par y timeframe (máximo de Binance por petición)
LIVE_CAPITAL = Decimal("100")  # una cuenta por estrategia (antes 20/50/100: mismos trades x3)
PRINCIPAL = "principal"  # tu cuenta de 40 USD: copia solo lo que ya ganó en vivo
PRINCIPAL_MAX_OPEN = 5  # 9-nov: más pares en reversion_4h → más señales
PRINCIPAL_LEVERAGE = Decimal(3)
# Se siguen sus precios para cerrar lo abierto, pero no abren más: mercados que cierran el fin de semana.
NO_ENTRY = {"GOLDUSDT", "BRENTUSDT"}
CHAMPION_MIN_TRADES = 5
CHAMPION_MIN_PF = Decimal("1.1")  # 5-nov: copiar lo que gana en vivo (antes 1.3 dejaba fuera a ema_rsi_4h)
STREAK_WINDOW, STREAK_LOSSES, STREAK_PAUSE_MS = 10, 5, 48 * 3_600_000  # video "win rate": 5 de 10 → parar


def two_sided(name: str) -> bool:
    """La copia es paper 1x estilo futuros: sigue a las ganadoras en largo y en corto, y sin un
    filtro de BTC propio (cada estrategia ya aplica el suyo). Pedido de José, 4-nov: copiar lo que
    funciona en el torneo, no solo los largos."""
    return True


def losers(trades) -> set[str]:
    """Aprende sola qué sacar: ≥4 cierres en vivo, PnL neto < 0 y gana menos de 0,8 veces lo que pierde."""
    seen, by = set(), {}
    for t in trades:
        key = (t.strategy, t.symbol, t.opened_ts)
        if t.strategy.startswith(PRINCIPAL) or key in seen:
            continue
        seen.add(key)
        by.setdefault(t.strategy, []).append(t.pnl)
    out = set()
    for name, pnls in by.items():
        wins = sum((p for p in pnls if p > 0), Decimal(0))
        losses = -sum((p for p in pnls if p < 0), Decimal(0))
        if len(pnls) >= 4 and wins - losses < 0 and wins < losses * Decimal("0.8"):
            out.add(name)
    return out


def champions(trades, benched: set[str]) -> set[str]:
    """Fuentes con ventaja comprobada: en LARGOS (spot) o en ambos lados si son de futuros.

    Cuenta cada operación una vez (antes había 3 cuentas por estrategia) y exige
    ≥5 cierres, PnL neto > 0 y factor de beneficio ≥ 1.3 ya con comisiones.
    """
    seen, by = set(), {}
    for t in trades:
        key = (t.strategy, t.symbol, t.opened_ts)
        if (t.side != "LONG" and not two_sided(t.strategy)) or t.strategy.startswith(PRINCIPAL) or key in seen:
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
        self.activity: deque[dict] = deque(maxlen=300)  # lo que hizo o decidió, en frases (panel "Actividad")
        self._checked = {"barras": 0, "senales": 0, "bloqueadas": 0}

    def note(self, kind: str, text: str, symbol: str | None = None) -> None:
        self.activity.appendleft({"ts": int(time.time() * 1000), "tipo": kind, "par": symbol, "texto": text})

    # --- arranque -----------------------------------------------------
    def restore(self) -> None:
        with self.session_factory() as db:
            self.accounts = store.load_accounts(db, [s.name for s in STRATEGIES], (LIVE_CAPITAL,))
            for strategy in STRATEGIES:
                if strategy.fee_rate is not None and (strategy.name, LIVE_CAPITAL) in self.accounts:
                    self.accounts[(strategy.name, LIVE_CAPITAL)].fee_rate = strategy.fee_rate
            self.accounts.update(store.load_accounts(db, [PRINCIPAL], (self.principal_capital,)))
            copy = self.accounts.get((PRINCIPAL, self.principal_capital))
            if copy is not None:  # 5-nov, José: 3x como su copy trading de BingX (paper, futuros maker)
                copy.leverage, copy.fee_rate = PRINCIPAL_LEVERAGE, Decimal("0.0002")
                flag = Path("data/reset_principal.flag")
                if flag.exists():  # empezar "Tu cuenta" de 0 sin borrar el historial
                    n = store.reset_account(db, copy, f"{PRINCIPAL}_hasta_{time.strftime('%Y%m%d')}")
                    flag.rename(flag.with_suffix(".done"))
                    self.note("aprende", f"Tu cuenta empieza de 0: {n} operaciones viejas archivadas")
        self.sync_brain()

    def sync_brain(self) -> None:
        """Toma del cerebro las estrategias aprobadas y la banca (se llama tras cada ciclo)."""
        from app.brain.evolve import EVOLVED_CAPITAL, live_strategies

        with self.session_factory() as db:
            evolved, self.benched = live_strategies(db)
            if evolved:
                self.accounts.update(store.load_accounts(db, [s.name for s in evolved], (Decimal(EVOLVED_CAPITAL),)))
            trades = store.closed_trades(db)
            fresh = losers(trades) - self.benched
            if fresh:
                self.note("aprende", f"Saca del torneo por perder en vivo: {', '.join(sorted(fresh))}.")
            self.benched |= losers(trades)
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
        """La cuenta de copia entra solo si la fuente está comprobada (largo; o ambos lados si es de futuros)."""
        account = self.principal
        futures = two_sided(source)
        if (account is None or (side != "LONG" and not futures) or source not in self.champions
                or f"{source}|{symbol}" in self.benched or symbol in account.positions
                or len(account.positions) >= PRINCIPAL_MAX_OPEN or symbol not in self.prices
                or (not futures and not self.btc_ok())  # spot: con BTC bajo su SMA20 no compra
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
        """Carga el historial de velas en paralelo (en serie tardaba ~2 min tras cada reinicio)."""
        from concurrent.futures import ThreadPoolExecutor

        now_ms = int(time.time() * 1000)

        def load(job: tuple[str, str]) -> None:
            symbol, tf = job
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

        jobs = [(s, tf) for s in self.symbols for tf in self.timeframes]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(load, jobs))  # una falla se propaga como antes (reintenta el bucle)
        for symbol in self.symbols:
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
            if symbol == "BTCUSDT":
                real.in_background(real.close_stale, note=self.note)
        tf_ms = TF_MINUTES[tf] * 60_000
        close_ts = bar.ts + tf_ms
        price = self.prices.get(symbol, dec(bar.c))
        running = self._running()
        if tf == "1h" and symbol == "BTCUSDT":
            c = self._checked
            self.note("revision", f"Revisión de la hora: {len(self.strategies)} estrategias sobre {len(self.prices)} pares, "
                                  f"{c['barras']} velas cerradas, {c['senales']} señales, {c['bloqueadas']} bloqueadas por filtros.")
            self._checked = {"barras": 0, "senales": 0, "bloqueadas": 0}
        self._checked["barras"] += 1
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
                if signal is not None:
                    self._checked["senales"] += 1
                if signal is not None and ((regime is True and not self.btc_ok()) or (regime == "bear" and self.btc_ok())):
                    self._checked["bloqueadas"] += 1
                    self.note("bloqueada", f"{strategy.name} quería {signal.side} en {symbol}, pero BTC "
                                           f"{'está bajo' if regime is True else 'está sobre'} su SMA20 diaria.", symbol)
                    continue
                if signal is not None and self.paused(strategy.name, close_ts):
                    self._checked["bloqueadas"] += 1
                    self.note("bloqueada", f"{strategy.name} quería {signal.side} en {symbol}, pero está en pausa (perdió 5 de 10).", symbol)
                    continue
                if (signal is None or not running or strategy.name in self.benched or symbol in NO_ENTRY
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
                    self.note("abre", f"{strategy.name} abrió {signal.side} en {symbol} a {price} "
                                      f"({float(opened.notional):.2f} USD).", symbol)
                    if strategy.name == real.SOURCE and signal.side == "LONG":
                        real.in_background(real.open_long, symbol, note=self.note)
                    copied = self.mirror(strategy.name, symbol, signal.side, opened.stop, opened.take_profit, close_ts)
                    if copied:
                        self.note("copia", f"La cuenta de copia siguió a {strategy.name}: {signal.side} en {symbol}.", symbol)

    def _close(self, account, symbol: str, price: Decimal, reason: str) -> None:
        db_id = account.positions[symbol].db_id
        trade = account.close(symbol, price, int(time.time() * 1000), reason)
        with self.session_factory() as db:
            store.save_close(db, account, db_id, trade)
        if trade is not None:
            self.note("cierra", f"{account.strategy} cerró {trade.side} en {symbol} ({reason}): "
                                f"{'+' if trade.pnl > 0 else ''}{float(trade.pnl):.2f} USD.", symbol)
        alerts.on_close(account.strategy, "Cuenta principal", symbol, trade)
        if trade is not None:
            self._record(account.strategy, trade.pnl > 0, trade.closed_ts)
            if account.strategy == real.SOURCE and trade.side == "LONG":
                real.in_background(real.close_long, symbol, reason, note=self.note)
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
                # tras un corte corto no hace falta recargar 75 historiales: solo si pasaron >30 min
                if time.time() - getattr(self, "_seeded_at", 0) > 1800:
                    await asyncio.to_thread(self.seed)
                    self._seeded_at = time.time()
                await asyncio.to_thread(self.close_orphans)
                async with websockets.connect(self.stream_url(), ping_interval=30, ping_timeout=60) as ws:
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

    def pair_view(self, symbol: str) -> dict:
        """Lo que el bot ve y piensa de un par: tendencia, movimiento, posiciones y cada estrategia."""
        h1 = self.bars.get((symbol, "1h"), [])
        d1 = self.bars.get((symbol, "1d"), [])
        last = float(self.prices.get(symbol) or (h1[-1].c if h1 else 0))
        out: dict = {"par": symbol, "precio": last,
                     "cambio_24h": round((last / h1[-24].c - 1) * 100, 2) if len(h1) >= 24 and last else None,
                     "regimen": self.regimes[symbol].labels[-1] if symbol in self.regimes and self.regimes[symbol].labels else "sin datos"}
        closes = [b.c for b in d1]
        if len(closes) >= 200:
            sma50, sma200 = sum(closes[-50:]) / 50, sum(closes[-200:]) / 200
            out["tendencia"] = ("alcista" if last > sma50 > sma200 else "bajista" if last < sma50 < sma200 else "mixta")
        # movimiento de 4 h en desviaciones (la regla de la reversión entra a ±3σ)
        c = [b.c for b in h1]
        if len(c) > 300:
            moves = [c[i] / c[i - 4] - 1 for i in range(len(c) - 300, len(c))]
            mean = sum(moves) / len(moves)
            sd = (sum((m - mean) ** 2 for m in moves) / len(moves)) ** 0.5
            out["movimiento_4h_sigma"] = round(moves[-1] / sd, 2) if sd else None
        out["posiciones"] = [
            {"cuenta": name, "lado": p.side, "entrada": float(p.entry), "abierta": p.opened_ts,
             "pnl": round(float(p.value(self.prices.get(symbol, p.entry)) - p.notional), 2),
             "stop": float(p.stop) if p.stop is not None else None, "objetivo": float(p.take_profit) if p.take_profit is not None else None}
            for (name, _), acc in self.accounts.items() for sym, p in acc.positions.items() if sym == symbol
        ]
        views = []
        waiting = self.status()["waiting"]
        for st in self.strategies:
            allowed = getattr(st, "symbols", None)
            if allowed and symbol not in allowed:
                continue
            series = self.bars.get((symbol, st.timeframe), [])
            try:
                sig = st.signals(series)[-1] if len(series) >= 2 else None
            except Exception:  # noqa: BLE001
                sig = None
            held = any(n == st.name and symbol in a.positions for (n, _), a in self.accounts.items())
            if held:
                text = "en posición"
            elif st.name in self.benched or f"{st.name}|{symbol}" in self.benched:
                text = "en la banca (no abre)"
            elif sig is not None:
                text = f"señal {sig.side} en la última vela de {st.timeframe}"
            elif st.name in waiting:
                text = waiting[st.name]
            else:
                text = f"sin señal (revisa cada vela de {st.timeframe})"
            views.append({"estrategia": st.name, "temporalidad": st.timeframe, "estado": text})
        out["estrategias"] = views
        return out

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
