"""Copia en papel de traders del copy trading de Binance (pedido de José, 9-nov).

Binance publica el historial de posiciones de cada trader líder. El bot lo lee cada 5 min y,
desde el momento en que empezó a mirar (sin mirar atrás), cada posición que el trader cierra
se apunta en una cuenta de 40 USD por trader: 10 % del saldo como margen, su apalancamiento
(tope 5x), comisión taker 0,05 % y 0,05 % de deslizamiento por lado. Así se ve quién gana de
verdad desde hoy. Con 10 o más copias y saldo bajo 40, el trader queda "en la banca".
Solo lectura: no envía órdenes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

URL = "https://www.binance.com/bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/position-history"
STATE = Path("data/copy_traders.json")
CAPITAL, MARGIN_PCT, MAX_LEV = 40.0, 0.10, 5.0
COST = 2 * 0.0005 + 2 * 0.0005  # comisión + deslizamiento, ida y vuelta
EVERY_SECONDS = 300
BENCH_AFTER = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "clienttype": "web",
           "content-type": "application/json"}


def traders() -> dict[str, str]:
    out = {}
    for item in settings.copy_traders.split(","):
        if "|" in item:
            name, pid = item.rsplit("|", 1)
            out[pid.strip()] = name.strip()
    return out


def load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"inicio": int(time.time() * 1000), "traders": {}}


def history(client, pid: str) -> list[dict]:
    r = client.post(URL, headers=HEADERS, timeout=20,
                    json={"portfolioId": pid, "pageNumber": 1, "pageSize": 50, "sort": "OPENING"})
    data = r.json()
    if data.get("code") != "000000":
        raise RuntimeError(f"binance copy {pid}: {data.get('code')} {data.get('message')}")
    return (data.get("data") or {}).get("list") or []


def apply(state: dict, pid: str, name: str, rows: list[dict]) -> list[dict]:
    """Apunta las posiciones cerradas nuevas (abiertas después de `inicio`). Devuelve las añadidas."""
    t = state["traders"].setdefault(pid, {"nombre": name, "saldo": CAPITAL, "copias": [], "vistas": []})
    t["nombre"] = name
    seen, added = set(t["vistas"]), []
    for p in sorted(rows, key=lambda x: x.get("closed") or 0):
        key = str(p.get("positionId"))
        if p.get("status") != "All Closed" or key in seen or int(p.get("opened") or 0) < state["inicio"]:
            continue
        try:
            entry, exit_ = float(p["avgCost"]), float(p["avgClosePrice"])
            lev = min(float(p.get("leverage") or 1), MAX_LEV)
        except (KeyError, TypeError, ValueError):
            continue
        side = 1 if str(p.get("side", "")).lower() == "long" else -1
        pnl = t["saldo"] * MARGIN_PCT * lev * (side * (exit_ / entry - 1) - COST)
        t["saldo"] = round(t["saldo"] + pnl, 4)
        trade = {"par": p.get("symbol"), "lado": "LONG" if side > 0 else "SHORT", "abre": int(p["opened"]),
                 "cierra": int(p.get("closed") or 0), "x": lev, "pnl": round(pnl, 4)}
        t["copias"].append(trade)
        t["vistas"].append(key)
        seen.add(key)
        added.append(trade)
    t["vistas"] = t["vistas"][-500:]
    return added


def board(state: dict) -> list[dict]:
    out = []
    for pid, t in state.get("traders", {}).items():
        c = t["copias"]
        wins = sum(1 for x in c if x["pnl"] > 0)
        out.append({"id": pid, "nombre": t["nombre"], "saldo": round(t["saldo"], 2), "copias": len(c),
                    "acierto": round(wins / len(c) * 100, 1) if c else None,
                    "banca": len(c) >= BENCH_AFTER and t["saldo"] < CAPITAL, "ultimas": c[-5:][::-1]})
    return sorted(out, key=lambda x: -x["saldo"])


def run_once(client=None) -> int:
    client = client or httpx
    state = load()
    n = 0
    for pid, name in traders().items():
        try:
            added = apply(state, pid, name, history(client, pid))
            n += len(added)
            for tr in added:
                note(f"{name}: {tr['lado']} {tr['par']} {tr['x']:g}x → {tr['pnl']:+.2f} USD")
        except Exception as exc:  # noqa: BLE001 — un trader que falla no frena a los demás
            logger.warning("binance copy: %s failed (%s)", name, exc)
        time.sleep(1)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return n


def note(text: str) -> None:
    try:
        from app.lab import live

        if live.runner:
            live.runner.note("copia", text)
    except Exception:  # noqa: BLE001
        pass


async def copy_loop(stop_event: asyncio.Event) -> None:
    if not traders():
        return
    while not stop_event.is_set():
        try:
            n = await asyncio.to_thread(run_once)
            logger.info("binance copy: %s new closed positions", n)
        except Exception as exc:  # noqa: BLE001
            logger.warning("binance copy: cycle failed (%s)", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=EVERY_SECONDS)
        except TimeoutError:
            pass
