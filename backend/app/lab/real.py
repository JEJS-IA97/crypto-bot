"""Dinero real en Binance Spot, solo con lo comprobado (decisión de José, 9-nov-2026).

Únicamente las COMPRAS de `reversion_spot_compras` (caída extrema de 2, 4 u 8 h) en 14 monedas (backtest Spot, 250 días,
637 operaciones, PF 1,79 con comisión 0,1 %). Todo lo demás (torneo, Tu cuenta, traders copiados,
apuestas) sigue en papel. Cuando la estrategia del torneo abre un LONG, aquí se compra REAL_USD
a mercado; cuando la cierra (4 h, stop u objetivo), aquí se vende lo comprado.

Candados: ALLOW_LIVE_TRADING=true en .env (solo José lo pone), máximo REAL_MAX_OPEN posiciones,
saldo USDT suficiente, y si la pérdida realizada del día (UTC) llega a REAL_DAILY_LOSS se deja de
comprar hasta el día siguiente. Las posiciones se guardan en data/real_positions.json para que
un reinicio no las olvide.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

SOURCE = "reversion_spot_compras"
REAL_USD = Decimal("6")
REAL_MAX_OPEN = 3
REAL_DAILY_LOSS = Decimal("3")
STATE = Path("data/real_positions.json")
_lock = threading.Lock()


def enabled() -> bool:
    return bool(settings.allow_live_trading and settings.binance_api_key and settings.binance_api_secret)


def _client():
    from app.services.binance_spot_client import BinanceSpotClient

    return BinanceSpotClient(settings.binance_api_key, settings.binance_api_secret, base_url="https://api.binance.com")


def load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"abiertas": {}, "cerradas": []}


def _save(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def lost_today(state: dict, now: float | None = None) -> Decimal:
    day = time.strftime("%Y-%m-%d", time.gmtime(now or time.time()))
    pnl = sum((Decimal(c["pnl"]) for c in state["cerradas"] if c["dia"] == day), Decimal(0))
    return -pnl if pnl < 0 else Decimal(0)


def received_qty(order: dict, base: str) -> Decimal:
    """Cantidad que de verdad quedó en la cuenta (Binance cobra la comisión en la moneda comprada)."""
    qty = Decimal(order.get("executedQty") or "0")
    for f in order.get("fills") or []:
        if f.get("commissionAsset") == base:
            qty -= Decimal(f["commission"])
    return qty


def floor_step(qty: Decimal, step: str) -> Decimal:
    s = Decimal(step).normalize()
    return (qty / s).to_integral_value(rounding=ROUND_DOWN) * s if s > 0 else qty


def _step(client, symbol: str) -> str:
    info = client.get_symbol_info(symbol)
    for f in info.get("filters", []):
        if f.get("filterType") == "LOT_SIZE":
            return f["stepSize"]
    return "0.00000001"


def open_long(symbol: str, note=print, client=None) -> dict | None:
    if not enabled():
        return None
    with _lock:
        state = load()
        if symbol in state["abiertas"] or len(state["abiertas"]) >= REAL_MAX_OPEN:
            return None
        if lost_today(state) >= REAL_DAILY_LOSS:
            note("real", f"Real: no compro {symbol}, hoy ya se perdieron {lost_today(state)} USD (tope {REAL_DAILY_LOSS}).")
            return None
        client = client or _client()
        try:
            free = next((Decimal(b["free"]) for b in client.get_account()["balances"] if b["asset"] == "USDT"), Decimal(0))
            if free < REAL_USD:
                note("real", f"Real: no compro {symbol}, solo hay {free} USDT libres.")
                return None
            order = client.create_order(symbol, "BUY", "MARKET", quote_order_qty=str(REAL_USD))
        except Exception as exc:  # noqa: BLE001
            note("real", f"Real: Binance rechazó la compra de {symbol} ({str(exc)[:120]}).")
            logger.warning("real: buy %s failed (%s)", symbol, exc)
            return None
        base = symbol[:-4]
        qty = received_qty(order, base)
        cost = Decimal(order.get("cummulativeQuoteQty") or REAL_USD)
        pos = {"qty": str(qty), "costo": str(cost), "abre": int(time.time() * 1000), "orden": order.get("orderId")}
        state["abiertas"][symbol] = pos
        _save(state)
    note("real", f"REAL: compré {qty} {base} por {cost:.2f} USDT en Binance.")
    return pos


def close_long(symbol: str, reason: str, note=print, client=None) -> dict | None:
    if not enabled():
        return None
    with _lock:
        state = load()
        pos = state["abiertas"].get(symbol)
        if pos is None:
            return None
        client = client or _client()
        try:
            qty = floor_step(Decimal(pos["qty"]), _step(client, symbol))
            order = client.create_order(symbol, "SELL", "MARKET", quantity=str(qty))
        except Exception as exc:  # noqa: BLE001
            note("real", f"Real: Binance rechazó la venta de {symbol} ({str(exc)[:120]}). Se reintenta en el próximo cierre.")
            logger.warning("real: sell %s failed (%s)", symbol, exc)
            return None
        got = Decimal(order.get("cummulativeQuoteQty") or "0")
        for f in order.get("fills") or []:
            if f.get("commissionAsset") == "USDT":
                got -= Decimal(f["commission"])
        pnl = got - Decimal(pos["costo"])
        closed = {**pos, "par": symbol, "recibido": str(got), "pnl": str(pnl), "motivo": reason,
                  "cierra": int(time.time() * 1000), "dia": time.strftime("%Y-%m-%d", time.gmtime())}
        state["cerradas"].append(closed)
        del state["abiertas"][symbol]
        _save(state)
    note("real", f"REAL: vendí {symbol} ({reason}): {'+' if pnl > 0 else ''}{pnl:.2f} USDT.")
    return closed


_balance_cache: dict = {}


def balance(prices: dict | None = None, ttl: float = 30) -> dict:
    """Saldo REAL de la cuenta Spot de Binance en USDT (lo que el bot puede usar), cacheado `ttl` s."""
    if not (settings.binance_api_key and settings.binance_api_secret):
        return {"error": "sin clave de Binance"}
    hit = _balance_cache.get("v")
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    try:
        client = _client()
        rows = [b for b in client.get_account()["balances"] if Decimal(b["free"]) + Decimal(b["locked"]) > 0]
        tickers = {t["symbol"]: Decimal(t["price"]) for t in client._request("GET", "/v3/ticker/price")}
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "-2015" in msg:  # la clave está restringida por IP y la PC cambió de internet/VPN
            try:
                import httpx

                ip = httpx.get("https://api.ipify.org", timeout=5).text.strip()
            except Exception:  # noqa: BLE001
                ip = "desconocida"
            out = {"error": f"Binance rechaza la IP actual de la PC ({ip}). Agrégala a la clave API o vuelve a la red/VPN de antes.",
                   "bloqueo_ip": ip}
            _balance_cache["v"] = (time.time(), out)
            return out
        return {"error": msg[:200]}
    assets, total = [], Decimal(0)
    for b in rows:
        asset, qty = b["asset"], Decimal(b["free"]) + Decimal(b["locked"])
        name = asset[2:] if asset.startswith("LD") else asset  # LDxxx = el mismo activo en Simple Earn
        px = Decimal(1) if name in ("USDT", "USDC", "FDUSD") else tickers.get(f"{name}USDT")
        value = qty * px if px is not None else None
        if value is not None:
            total += value
        assets.append({"activo": asset, "cantidad": str(qty), "usdt": float(round(value, 2)) if value is not None else None,
                       "earn": asset.startswith("LD")})
    usdt = next((Decimal(b["free"]) for b in rows if b["asset"] == "USDT"), Decimal(0))
    out = {"total_usdt": float(round(total, 2)), "usdt_libre": float(round(usdt, 2)),
           "activos": sorted(assets, key=lambda a: -(a["usdt"] or 0)), "ts": int(time.time() * 1000)}
    _balance_cache["v"] = (time.time(), out)
    return out


def in_background(fn, *args, **kwargs) -> None:
    """Las órdenes salen en otro hilo para no frenar el feed de precios."""
    threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()


def close_stale(note=print, max_hours: float = 6) -> None:
    """Red de seguridad: si la posición del torneo se perdió (p. ej. un reinicio), vende igual tras 6 h."""
    if not enabled():
        return
    now = time.time() * 1000
    for symbol, pos in list(load()["abiertas"].items()):
        if now - pos["abre"] > max_hours * 3_600_000:
            close_long(symbol, "tiempo máximo", note=note)
