from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SimulationAccount(Base):
    __tablename__ = "simulation_accounts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        default="Default Simulation",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    balance: Mapped["SimulationBalance | None"] = relationship(
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )

    positions: Mapped[list["SimulationPosition"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    trades: Mapped[list["SimulationTrade"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    arbitrages: Mapped[list["SimulationArbitrage"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class SimulationBalance(Base):
    __tablename__ = "simulation_balances"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_accounts.id"),
        unique=True,
    )

    available_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("20.00"),
    )

    invested_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00"),
    )

    realized_pnl_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0.00"),
    )

    account: Mapped["SimulationAccount"] = relationship(
        back_populates="balance",
    )


class SimulationPosition(Base):
    __tablename__ = "simulation_positions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_accounts.id"),
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        default=Decimal("0"),
    )

    average_entry_price: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        default=Decimal("0"),
    )

    account: Mapped["SimulationAccount"] = relationship(
        back_populates="positions",
    )


class SimulationTrade(Base):
    __tablename__ = "simulation_trades"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_accounts.id"),
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    side: Mapped[TradeSide] = mapped_column(
        SqlEnum(TradeSide),
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
    )

    total_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
    )

    fee_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )

    realized_pnl_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    account: Mapped["SimulationAccount"] = relationship(
        back_populates="trades",
    )


class SimulationArbitrage(Base):
    __tablename__ = "simulation_arbitrages"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_accounts.id"),
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    base_asset: Mapped[str] = mapped_column(
        String(20),
    )

    quote_currency: Mapped[str] = mapped_column(
        String(10),
    )

    buy_exchange: Mapped[str] = mapped_column(
        String(30),
    )

    sell_exchange: Mapped[str] = mapped_column(
        String(30),
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
    )

    buy_price: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
    )

    sell_price: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
    )

    buy_total_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
    )

    buy_fee_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
    )

    sell_total_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
    )

    sell_fee_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
    )

    net_profit_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    account: Mapped["SimulationAccount"] = relationship(
        back_populates="arbitrages",
    )


class SimulationMarketPrice(Base):
    __tablename__ = "simulation_market_prices"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
    )

    price_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 12),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )