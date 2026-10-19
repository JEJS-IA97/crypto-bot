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
    strategies = getattr(live.runner, "strategies", STRATEGIES)
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


@router.get("/live")
def live_board(db: Session = Depends(get_db)) -> dict[str, Any]:
    runner = live.runner
    return {
        "feed": runner.status() if runner else {"connected": False, "enabled": False},
        "rows": store.leaderboard(db, labels()),
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
    from app.signals.telegram import TelegramSignal, _chats

    rows = db.scalars(select(TelegramSignal).order_by(TelegramSignal.id.desc()).limit(min(limit, 200))).all()
    return {
        "configured": bool(settings.telegram_api_id and settings.telegram_api_hash and _chats()),
        "signals": [
            {"chat": r.chat_title, "text": r.text[:280], "parsed": r.parsed, "outcome": r.outcome,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ],
    }
