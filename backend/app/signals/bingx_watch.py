"""Aprender de tu cuenta de BingX (solo lectura): qué cerraste o copiaste, cuánto duró, con qué
apalancamiento y si ganó, para que el cerebro lo compare con sus estrategias.

Nunca envía órdenes: el cliente solo hace GET. Pon en .env una clave de BingX con permiso de
SOLO LECTURA (BINGX_API_KEY / BINGX_API_SECRET). Sin clave, el módulo no hace nada.
Endpoints (futuros perpetuos): /openApi/swap/v2/user/income (qué pares tuvieron PnL) y
/openApi/swap/v1/trade/positionHistory (posiciones cerradas por par).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE = "https://open-api.bingx.com"
OUT = Path("data/bingx_trades.json")
DAYS = 30
EVERY_SECONDS = 3600


def _get(client, path: str, **params) -> dict:
    """GET firmado (HMAC-SHA256 de la query ordenada). Solo GET: no existe camino para operar."""
    params = {**params, "timestamp": int(time.time() * 1000)}
    query = urlencode(sorted(params.items()))
    sig = hmac.new(settings.bingx_api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    data = client.get(f"{BASE}{path}?{query}&signature={sig}", headers={"X-BX-APIKEY": settings.bingx_api_key}, timeout=20).json()
    if data.get("code") not in (0, "0"):
        raise RuntimeError(f"bingx {path}: {data.get('code')} {data.get('msg')}")
    return data


def traded_symbols(client, start_ms: int, end_ms: int) -> list[str]:
    rows = _get(client, "/openApi/swap/v2/user/income", incomeType="REALIZED_PNL",
                startTime=start_ms, endTime=end_ms, limit=1000).get("data") or []
    return sorted({r["symbol"] for r in rows if r.get("symbol")})


def positions(client, symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    data = _get(client, "/openApi/swap/v1/trade/positionHistory", symbol=symbol, startTs=start_ms, endTs=end_ms,
                pageIndex=1, pageSize=100).get("data") or {}
    rows = data.get("positionHistory", data) if isinstance(data, dict) else data
    out = []
    for r in rows or []:
        try:
            out.append({
                "par": r["symbol"], "lado": (r.get("positionSide") or "").upper(),
                "abre": int(r["openTime"]), "cierra": int(r.get("updateTime") or r["openTime"]),
                "entrada": float(r.get("avgPrice") or 0), "salida": float(r.get("avgClosePrice") or 0),
                "pnl": float(r.get("netProfit") or r.get("realisedProfit") or 0),
                "apalancamiento": float(r.get("leverage") or 1),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def standard_contract(client, start_ms: int, end_ms: int) -> list[dict]:
    """Futuros "estándar" de BingX (donde suele vivir el copy trading): órdenes cerradas con PnL."""
    data = _get(client, "/openApi/contract/v1/allOrders", startTime=start_ms, endTime=end_ms, limit=500).get("data") or []
    rows = data.get("orders", data) if isinstance(data, dict) else data
    out = []
    for r in rows or []:
        pnl = r.get("profit") or r.get("realizedPnl") or r.get("realisedPNL")
        if pnl in (None, "", "0", 0):
            continue
        try:
            out.append({"par": r.get("symbol", "?"), "lado": (r.get("positionSide") or r.get("side") or "").upper(),
                        "abre": int(r.get("time") or r.get("updateTime") or 0),
                        "cierra": int(r.get("updateTime") or r.get("time") or 0),
                        "entrada": float(r.get("avgPrice") or 0), "salida": float(r.get("avgPrice") or 0),
                        "pnl": float(pnl), "apalancamiento": float(r.get("leverage") or 1), "cuenta": "estándar"})
        except (TypeError, ValueError):
            continue
    return out


def style(rows: list[dict]) -> dict:
    if not rows:
        return {}
    pnls = [r["pnl"] for r in rows]
    wins, losses = [p for p in pnls if p > 0], [-p for p in pnls if p <= 0]
    hours = [(r["cierra"] - r["abre"]) / 3_600_000 for r in rows]
    open_hours = Counter(datetime.fromtimestamp(r["abre"] / 1000, timezone.utc).hour for r in rows)
    return {
        "posiciones": len(rows),
        "acierto": round(len(wins) / len(rows) * 100, 1),
        "pnl_total": round(sum(pnls), 4),
        "payoff": round(statistics.mean(wins) / statistics.mean(losses), 2) if wins and losses else None,
        "largos_pct": round(sum(1 for r in rows if r["lado"] == "LONG") / len(rows) * 100),
        "horas_mediana": round(statistics.median(hours), 2),
        "apalancamiento_mediano": statistics.median(r["apalancamiento"] for r in rows),
        "pares": [p for p, _ in Counter(r["par"] for r in rows).most_common(5)],
        "horas_utc_de_entrada": [h for h, _ in open_hours.most_common(3)],
    }


def lessons(st: dict) -> list[str]:
    if not st:
        return []
    return [f"Cuenta BingX de José (últimos {DAYS} días): {st['posiciones']} posiciones, acierto {st['acierto']} %, "
            f"PnL {st['pnl_total']:+} USDT, payoff {st['payoff']}, {st['largos_pct']} % largos, duración mediana "
            f"{st['horas_mediana']} h, apalancamiento {st['apalancamiento_mediano']}x, pares {', '.join(st['pares'])}, "
            f"entra sobre todo a las {st['horas_utc_de_entrada']} UTC."]


def run_once(client=None) -> dict:
    client = client or httpx
    end = int(time.time() * 1000)
    start = end - DAYS * 86_400_000
    rows, diag = [], {}
    try:
        symbols = traded_symbols(client, start, end)
        diag["perpetuos_pares_con_pnl"] = len(symbols)
    except Exception as exc:  # noqa: BLE001
        symbols, diag["perpetuos"] = [], str(exc)[:200]
    for symbol in symbols:
        try:
            rows += positions(client, symbol, start, end)
        except Exception as exc:  # noqa: BLE001 — un par que falla no tumba el resto
            logger.warning("bingx: %s failed (%s)", symbol, exc)
    try:
        std = standard_contract(client, start, end)
        diag["estandar_ordenes_con_pnl"] = len(std)
        rows += std
    except Exception as exc:  # noqa: BLE001
        diag["estandar"] = str(exc)[:200]
    st = style(rows)
    report = {"actualizado": datetime.now(timezone.utc).isoformat(), "diagnostico": diag, "resumen": st,
              "posiciones": sorted(rows, key=lambda r: -r["cierra"])}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from app.brain.evolve import remember

        remember(lessons(st), datetime.now(timezone.utc))
    except Exception:  # noqa: BLE001
        logger.warning("bingx: could not write brain memory", exc_info=True)
    return report


async def bingx_loop(stop_event: asyncio.Event) -> None:
    if not (settings.bingx_api_key and settings.bingx_api_secret):
        logger.info("bingx: no read-only key (BINGX_API_KEY/SECRET), skipping")
        return
    while not stop_event.is_set():
        try:
            report = await asyncio.to_thread(run_once)
            logger.info("bingx: %s closed positions read", len(report["posiciones"]))
        except Exception as exc:  # noqa: BLE001
            logger.warning("bingx: read failed (%s)", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=EVERY_SECONDS)
        except TimeoutError:
            pass
