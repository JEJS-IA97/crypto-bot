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
from app.lab.strategies import STRATEGIES

router = APIRouter(prefix="/api/lab", tags=["Laboratorio"])

LABELS = {s.name: s.label for s in STRATEGIES}


@router.get("/strategies")
def strategies() -> list[dict[str, Any]]:
    return [
        {"name": s.name, "label": s.label, "timeframe": s.timeframe, "description": s.description}
        for s in STRATEGIES
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
        "rows": store.leaderboard(db, LABELS),
    }


@router.get("/trades")
def trades(limit: int = 50, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(LabTrade).order_by(LabTrade.id.desc()).limit(min(limit, 500))).all()
    return [
        {
            "id": r.id,
            "strategy": LABELS.get(r.strategy, r.strategy),
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
