"""Observatorio de traders que ganan: perfiles públicos de copy trading de OKX (sin claves).

Binance no expone historial de traders por API; OKX sí (endpoints públicos). Cada 12 h:
- toma los líderes con ≥180 días (Spot y perpetuos), su resultado del último año y lo que
  ganaron sus copiadores,
- en perpetuos lee sus últimas 100 posiciones cerradas y calcula su estilo (acierto, cuánto
  gana frente a lo que pierde, % de largos, duración, apalancamiento, qué opera),
- guarda todo en data/okx_traders.json y deja las lecciones en la memoria del cerebro.
Las posiciones abiertas salen sin símbolo en la API pública: no se pueden copiar en vivo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE = "https://www.okx.com/api/v5/copytrading/"
OUT = Path("data/okx_traders.json")
MIN_DAYS = 180
EVERY_SECONDS = 12 * 3600
OUR_COINS = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "LINK", "AVAX", "LTC"}


def _get(client, path: str, **params) -> list:
    data = client.get(BASE + path, params=params, timeout=20).json()
    if data.get("code") != "0":
        raise RuntimeError(f"okx {path}: {data.get('msg')}")
    return data.get("data") or []


def style(history: list[dict]) -> dict:
    """Estilo de un trader a partir de sus posiciones cerradas."""
    pnls = [float(h["pnl"]) for h in history if h.get("pnl")]
    if not pnls:
        return {}
    wins, losses = [p for p in pnls if p > 0], [-p for p in pnls if p <= 0]
    holds = [(int(h["closeTime"]) - int(h["openTime"])) / 3_600_000 for h in history if h.get("closeTime") and h.get("openTime")]
    levers = [float(h["lever"]) for h in history if h.get("lever")]
    coins = Counter(h["instId"].split("-")[0] for h in history if h.get("instId"))
    return {
        "posiciones": len(pnls),
        "acierto": round(len(wins) / len(pnls) * 100, 1),
        "payoff": round(statistics.mean(wins) / statistics.mean(losses), 2) if wins and losses else None,
        "largos_pct": round(sum(1 for h in history if h.get("posSide") == "long") / len(history) * 100),
        "horas_mediana": round(statistics.median(holds), 1) if holds else None,
        "apalancamiento_mediano": statistics.median(levers) if levers else None,
        "opera": [c for c, _ in coins.most_common(5)],
        "en_nuestros_pares_pct": round(sum(n for c, n in coins.items() if c in OUR_COINS) / max(sum(coins.values()), 1) * 100),
    }


def profiles(client=None, limit: int = 20) -> list[dict]:
    client = client or httpx
    out = []
    for inst in ("SPOT", "SWAP"):
        ranks = (_get(client, "public-lead-traders", instType=inst, sortType="overview", limit=limit) or [{}])[0].get("ranks", [])
        for r in ranks:
            if int(r.get("leadDays") or 0) < MIN_DAYS:
                continue
            row = {"mercado": "Spot" if inst == "SPOT" else "Perpetuos", "nombre": r["nickName"], "codigo": r["uniqueCode"],
                   "dias": int(r["leadDays"]), "pnl_usd": round(float(r["pnl"])), "retorno_pct": round(float(r["pnlRatio"]) * 100, 1),
                   "copiadores": int(r.get("copyTraderNum") or 0)}
            try:
                stats = _get(client, "public-stats", instType=inst, uniqueCode=r["uniqueCode"], lastDays="4")  # 4 = último año
                if stats:
                    s = stats[0]
                    row |= {"pnl_copiadores_usd": round(float(s.get("curCopyTraderPnl") or 0)),
                            "dias_gana": int(s.get("profitDays") or 0), "dias_pierde": int(s.get("lossDays") or 0)}
                if inst == "SWAP":
                    row |= style(_get(client, "public-subpositions-history", instType=inst, uniqueCode=r["uniqueCode"], limit="100"))
            except Exception as exc:  # noqa: BLE001 — un trader que falla no tumba el resto
                logger.warning("okx: %s failed (%s)", r.get("nickName"), exc)
            out.append(row)
    return out


def lessons(rows: list[dict]) -> list[str]:
    """Lo que tienen en común los que ganan y además hacen ganar a sus copiadores."""
    good = [r for r in rows if r.get("pnl_copiadores_usd", 0) > 0 and r.get("acierto") is not None]
    if not good:
        return []
    lines = [f"Observatorio OKX: {len(good)} traders con ≥{MIN_DAYS} días cuyos copiadores ganan."]
    lines.append(
        f"Acierto mediano {statistics.median(r['acierto'] for r in good):.0f} %, "
        f"payoff mediano {statistics.median(r['payoff'] for r in good if r.get('payoff')):.2f}, "
        f"largos {statistics.median(r['largos_pct'] for r in good):.0f} %, "
        f"duración mediana {statistics.median(r['horas_mediana'] for r in good if r.get('horas_mediana') is not None):.1f} h, "
        f"apalancamiento mediano {statistics.median(r['apalancamiento_mediano'] for r in good if r.get('apalancamiento_mediano')):.0f}x."
    )
    for r in sorted(good, key=lambda r: -r["pnl_copiadores_usd"])[:3]:
        lines.append(f"{r['nombre']} ({r['dias']} días, copiadores {r['pnl_copiadores_usd']:+,} USD): acierto {r['acierto']} %, "
                     f"payoff {r.get('payoff')}, {r['largos_pct']} % largos, {r.get('horas_mediana')} h, {r.get('apalancamiento_mediano')}x, opera {', '.join(r['opera'])}.")
    return lines


def run_once(client=None) -> list[dict]:
    rows = profiles(client)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"actualizado": datetime.now(timezone.utc).isoformat(), "traders": rows, "lecciones": lessons(rows)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from app.brain.evolve import remember

        remember(lessons(rows), datetime.now(timezone.utc))
    except Exception:  # noqa: BLE001
        logger.warning("okx: could not write brain memory", exc_info=True)
    return rows


async def okx_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            rows = await asyncio.to_thread(run_once)
            logger.info("okx: %s lead traders profiled", len(rows))
        except Exception as exc:  # noqa: BLE001
            logger.warning("okx: watch failed (%s)", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=EVERY_SECONDS)
        except TimeoutError:
            pass
