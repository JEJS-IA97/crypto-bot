"""Tablas del laboratorio (solo paper): estado de cada cuenta y sus trades."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import utc_now

MONEY = Numeric(30, 12)


class LabAccountState(Base):
    __tablename__ = "lab_accounts"
    __table_args__ = (UniqueConstraint("strategy", "capital"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy: Mapped[str] = mapped_column(String(60))
    capital: Mapped[Decimal] = mapped_column(MONEY)
    cash: Mapped[Decimal] = mapped_column(MONEY)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class LabTrade(Base):
    __tablename__ = "lab_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy: Mapped[str] = mapped_column(String(60), index=True)
    capital: Mapped[Decimal] = mapped_column(MONEY)
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(5))
    qty: Mapped[Decimal] = mapped_column(MONEY)
    entry: Mapped[Decimal] = mapped_column(MONEY)
    stop: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    notional: Mapped[Decimal] = mapped_column(MONEY)
    entry_fee: Mapped[Decimal] = mapped_column(MONEY)
    risk_usd: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    opened_ts: Mapped[int] = mapped_column(BigInteger)
    regime: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(8), default="OPEN", index=True)
    exit_price: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    closed_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    fees: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    r_multiple: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
