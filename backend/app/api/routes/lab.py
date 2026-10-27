"""Laboratorio: ranking del torneo (backtest y en vivo), trades y estado del feed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.lab import live, store
from app.lab.backtest import REPORT_JSON
from app.lab.models import LabTrade
from app.brain import evolve
from app.brain.analyst import labels
from app.config import settings
from app.lab.bars import TF_MINUTES
from app.lab.strategies import STRATEGIES

router = APIRouter(prefix="/api/lab", tags=["Laboratorio"])


@router.get("/strategies")
def strategies() -> list[dict[str, Any]]:
    strategies = getattr(live.runner, "strategies", None) or STRATEGIES
    return [
        {"name": s.name, "label": s.label, "timeframe": s.timeframe, "description": s.description}
        for s in strategies
    ]


@router.get("/backtest")
def backtest() -> dict[str, Any]:
    path = Path(REPORT_JSON)
    if not path.exists():
        raise HTTPException(404, "Aún no hay backtest: ejecuta python -m app.lab.backtest")
    return json.loads(path.read_text(encoding="utf-8"))


def _balances(db: Session, rows: list[dict[str, Any]], principal: dict[str, Any] | None) -> dict[str, Any]:
    """Cuenta principal (núcleo de tendencia, 40 USD), la copiadora de ganadoras y el torneo."""
    from app.services.decision_store import get_metrics

    try:
        m = get_metrics(db, account_id=settings.simulation_bot_account_id)
        main = {
            "initial": float(settings.configured_capital_usd),
            "balance": float(m["balance_usd"]),
            "available": float(m["available_usd"]),
            "realized": float(m["realized_pnl_usd"]),
            "unrealized": float(m["unrealized_pnl_usd"]),
            "open_positions": m["open_positions"],
        }
    except Exception:  # noqa: BLE001
        main = None
    runner = live.runner
    copier = None
    if principal is not None:
        account = runner.principal if runner else None
        copier = {
            "initial": principal["capital"],
            "balance": round(float(account.equity(runner.prices)), 2) if account else principal["capital"] + principal["net_pnl"],
            "available": round(float(account.cash), 2) if account else principal["cash"],
            "realized": principal["net_pnl"],
            "open_positions": principal["open_positions"],
            "trades": principal["trades"],
            "copies": sorted(runner.champions) if runner else [],
        }
    initial = sum(r["capital"] for r in rows)
    active = [a for k, a in runner.accounts.items() if k[0] != live.PRINCIPAL] if runner and runner.accounts else []
    equity = sum(float(a.equity(runner.prices)) for a in active) if active else initial + sum(r["net_pnl"] for r in rows)
    return {
        "main": main,
        "copier": copier,
        "tournament": {"initial": initial, "balance": round(equity, 2), "realized": round(sum(r["net_pnl"] for r in rows), 2),
                       "accounts": len(rows)},
    }


@router.get("/live")
def live_board(db: Session = Depends(get_db)) -> dict[str, Any]:
    runner = live.runner
    rows = store.leaderboard(db, labels())
    if runner and runner.accounts:  # solo lo que sigue en el torneo; lo retirado queda en el historial
        active = {(name, float(capital)) for name, capital in runner.accounts}
        rows = [r for r in rows if (r["strategy"], r["capital"]) in active]
    principal = next((r for r in rows if r["strategy"] == live.PRINCIPAL), None)
    rows = [r for r in rows if r["strategy"] != live.PRINCIPAL]
    return {
        "feed": runner.status() if runner else {"connected": False, "enabled": False},
        "rows": rows,
        "balances": _balances(db, rows, principal),
    }


@router.get("/trades")
def trades(limit: int = 50, symbol: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    query = select(LabTrade).order_by(LabTrade.id.desc()).limit(min(limit, 500))
    if symbol:
        query = query.where(LabTrade.symbol == symbol.upper())
    rows = db.scalars(query).all()
    return [
        {
            "id": r.id,
            "strategy": labels().get(r.strategy, r.strategy),
            "strategy_name": r.strategy,
            "capital": float(r.capital),
            "symbol": r.symbol,
            "side": r.side,
            "entry": float(r.entry),
            "stop": float(r.stop) if r.stop is not None else None,
            "take_profit": float(r.take_profit) if r.take_profit is not None else None,
            "status": r.status,
            "exit": float(r.exit_price) if r.exit_price is not None else None,
            "pnl": float(r.pnl) if r.pnl is not None else None,
            "r": float(r.r_multiple) if r.r_multiple is not None else None,
            "reason": r.reason,
            "regime": r.regime,
            "opened_ts": r.opened_ts,
            "closed_ts": r.closed_ts,
        }
        for r in rows
    ]


@router.get("/candles")
def candles(symbol: str = "BTCUSDT", tf: str = "1h", limit: int = 300) -> dict[str, Any]:
    """Velas cerradas que ve el torneo (WebSocket) para el gráfico del panel."""
    if tf not in TF_MINUTES:
        raise HTTPException(422, f"timeframe inválido: {tf}")
    bars = (getattr(live.runner, "bars", {}) or {}).get((symbol.upper(), tf), [])[-min(limit, 1000):]
    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "price": float(live.runner.prices[symbol.upper()]) if live.runner and symbol.upper() in live.runner.prices else None,
        "candles": [{"time": b.ts // 1000, "open": b.o, "high": b.h, "low": b.l, "close": b.c, "volume": b.v} for b in bars],
    }


@router.get("/brain")
def brain(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Lo que el cerebro probó, aprobó, retiró y lo que recuerda."""
    rows = db.scalars(select(evolve.BrainGenome).order_by(evolve.BrainGenome.id.desc())).all()
    names = labels()
    live_names = [r.name for r in rows if r.status == "live"]
    weights = evolve.confidence(store.closed_trades(db), live_names)
    memory = evolve.recent_memory(6000)
    diary_dir = Path(settings.brain_dir) / "diario"
    diaries = sorted(diary_dir.glob("*.md")) if diary_dir.exists() else []
    last_entry = diaries[-1].read_text(encoding="utf-8").split("\n## ")[-1] if diaries else ""
    return {
        "genomes": [
            {
                "name": r.name,
                "label": names.get(r.name) or evolve.Evolved(r.name, r.family, r.params).label
                if r.family in evolve.FAMILIES else names.get(r.name, r.name),
                "family": r.family,
                "params": r.params,
                "origin": r.origin,
                "status": r.status,
                "note": r.note,
                "metrics": r.metrics,
                "weight": weights.get(r.name, 0.0),
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
        "counts": {s: sum(1 for r in rows if r.status == s) for s in ("live", "banca", "retirada", "rechazada")},
        "memory": memory,
        "last_entry": "## " + last_entry if last_entry else "",
    }


@router.get("/telegram")
def telegram_signals(limit: int = 30, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Últimos mensajes leídos de tus grupos y qué hizo el bot con cada uno."""
    from app.signals.telegram import CHATS_FILE, TelegramSignal

    rows = db.scalars(select(TelegramSignal).order_by(TelegramSignal.id.desc()).limit(min(limit, 200))).all()
    from app.signals.verify import binance_pair, binance_symbols, channel_score

    channels: dict[str, dict[str, int]] = {}
    verified: dict[str, list[dict]] = {}
    for title, parsed in db.execute(select(TelegramSignal.chat_title, TelegramSignal.parsed)):
        if (parsed or {}).get("verificada"):
            verified.setdefault(title, []).append(parsed["verificada"])
        stats = channels.setdefault(title, {"mensajes": 0, "senales": 0, "ganadas": 0, "perdidas": 0})
        stats["mensajes"] += 1
        kind = (parsed or {}).get("kind", "cripto" if parsed else None)
        if kind in ("binaria", "cripto"):
            stats["senales"] += 1
        elif kind == "resultado":
            stats["ganadas" if parsed["result"].startswith("win") else "perdidas"] += 1
        elif kind == "informe":
            stats["ganadas"] += parsed["wins"]
            stats["perdidas"] += parsed["losses"]
    return {
        "channels": [{"chat": k, **v, **channel_score(verified.get(k, []))} for k, v in sorted(channels.items())],
        "assets": _assets(db, TelegramSignal, binance_symbols(), binance_pair),
        "configured": bool(settings.telegram_api_id and settings.telegram_api_hash),
        "dialogs": json.loads(CHATS_FILE.read_text(encoding="utf-8")) if CHATS_FILE.exists() else [],
        "signals": [
            {"chat": r.chat_title, "text": r.text[:280], "parsed": r.parsed, "outcome": r.outcome,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ],
    }


def _assets(db: Session, model, symbols: set[str], to_pair) -> list[dict[str, Any]]:
    """Divisas que mencionan tus grupos y si existen en Binance para seguirlas allá."""
    count: dict[tuple[str, bool], int] = {}
    for (parsed,) in db.execute(select(model.parsed)):
        if (parsed or {}).get("kind") == "binaria":
            key = (parsed["asset"], bool(parsed.get("otc")))
            count[key] = count.get(key, 0) + 1
    return sorted(
        ({"asset": a, "otc": otc, "senales": n, "binance": to_pair(a, symbols)} for (a, otc), n in count.items()),
        key=lambda r: -r["senales"],
    )


@router.get("/okx")
def okx_traders() -> dict[str, Any]:
    """Observatorio de traders de OKX con ≥180 días: estilo, resultado y lo que ganan sus copiadores."""
    from app.signals.okx_watch import OUT

    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"traders": [], "lecciones": []}


@router.get("/bets")
def bets(limit: int = 60, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Apuestas en paper: resumen por estrategia y últimas apuestas."""
    from app.bets.engine import BetPick, summary

    picks = db.scalars(select(BetPick).order_by(BetPick.kickoff.desc()).limit(min(limit, 300))).all()
    return {
        "resumen": summary(db),
        "odds_api": bool(settings.odds_api_key),
        "apuestas": [
            {"estrategia": p.strategy, "deporte": p.sport, "liga": p.league, "partido": p.match, "seleccion": p.selection,
             "inicio": p.kickoff.isoformat(), "cuota": float(p.odds), "prob_justa": float(p.fair_prob) if p.fair_prob else None,
             "estado": p.status, "pnl": float(p.pnl) if p.pnl is not None else None,
             "clv": float(p.clv_pct) if p.clv_pct is not None else None}
            for p in picks
        ],
    }
