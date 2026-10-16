"""Persistencia del torneo en vivo: las cuentas sobreviven a reinicios del bot."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lab.engine import Account, Position, Trade
from app.lab.metrics import summarize
from app.lab.models import LabAccountState, LabTrade
from app.models import utc_now


def load_accounts(db: Session, strategies: list[str], capitals) -> dict[tuple[str, Decimal], Account]:
    accounts: dict[tuple[str, Decimal], Account] = {}
    states = {(s.strategy, Decimal(s.capital).normalize()): s for s in db.scalars(select(LabAccountState))}
    for name in strategies:
        for capital in capitals:
            state = states.get((name, capital.normalize()))
            if state is None:
                state = LabAccountState(strategy=name, capital=capital, cash=capital)
                db.add(state)
            accounts[(name, capital)] = Account(name, capital, cash=Decimal(state.cash))
    db.commit()
    for row in db.scalars(select(LabTrade).where(LabTrade.status == "OPEN")):
        account = accounts.get((row.strategy, Decimal(row.capital).normalize()))
        if account is None:
            continue
        account.positions[row.symbol] = Position(
            symbol=row.symbol,
            side=row.side,
            qty=row.qty,
            entry=row.entry,
            stop=row.stop,
            take_profit=row.take_profit,
            notional=row.notional,
            entry_fee=row.entry_fee,
            opened_ts=row.opened_ts,
            regime=row.regime,
            risk_usd=row.risk_usd,
            db_id=row.id,
        )
    return accounts


def _save_cash(db: Session, account: Account) -> None:
    state = db.scalars(
        select(LabAccountState).where(
            LabAccountState.strategy == account.strategy,
            LabAccountState.capital == account.capital,
        )
    ).one()
    state.cash = account.cash
    state.updated_at = utc_now()


def save_open(db: Session, account: Account, position: Position) -> None:
    row = LabTrade(
        strategy=account.strategy,
        capital=account.capital,
        symbol=position.symbol,
        side=position.side,
        qty=position.qty,
        entry=position.entry,
        stop=position.stop,
        take_profit=position.take_profit,
        notional=position.notional,
        entry_fee=position.entry_fee,
        risk_usd=position.risk_usd,
        opened_ts=position.opened_ts,
        regime=position.regime,
    )
    db.add(row)
    _save_cash(db, account)
    db.commit()
    position.db_id = row.id


def save_close(db: Session, account: Account, db_id: int | None, trade: Trade) -> None:
    row = db.get(LabTrade, db_id) if db_id else None
    if row is not None:
        row.status = "CLOSED"
        row.exit_price = trade.exit
        row.closed_ts = trade.closed_ts
        row.pnl = trade.pnl
        row.fees = trade.fees
        row.r_multiple = trade.r_multiple
        row.reason = trade.reason
    _save_cash(db, account)
    db.commit()


def closed_trades(db: Session) -> list[Trade]:
    rows = db.scalars(select(LabTrade).where(LabTrade.status == "CLOSED")).all()
    return [
        Trade(
            strategy=r.strategy,
            capital=Decimal(r.capital),
            symbol=r.symbol,
            side=r.side,
            qty=r.qty,
            entry=r.entry,
            exit=r.exit_price,
            opened_ts=r.opened_ts,
            closed_ts=r.closed_ts,
            pnl=Decimal(r.pnl),
            fees=Decimal(r.fees),
            r_multiple=r.r_multiple,
            regime=r.regime,
            reason=r.reason or "",
        )
        for r in rows
    ]


def leaderboard(db: Session, labels: dict[str, str]) -> list[dict]:
    trades = closed_trades(db)
    states = db.scalars(select(LabAccountState)).all()
    open_rows = db.scalars(select(LabTrade).where(LabTrade.status == "OPEN")).all()
    rows = []
    for state in states:
        capital = Decimal(state.capital)
        mine = [t for t in trades if t.strategy == state.strategy and t.capital == capital]
        rows.append(
            {
                "strategy": state.strategy,
                "label": labels.get(state.strategy, state.strategy),
                "capital": float(capital),
                "cash": float(state.cash),
                "open_positions": sum(
                    1 for r in open_rows if r.strategy == state.strategy and Decimal(r.capital) == capital
                ),
                **summarize(mine, capital),
            }
        )
    return rows
