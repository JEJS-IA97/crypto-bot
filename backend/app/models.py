from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


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
        default=utc_now,
    )

    balance: Mapped[
        "SimulationBalance | None"
    ] = relationship(
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )

    positions: Mapped[
        list["SimulationPosition"]
    ] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    trades: Mapped[
        list["SimulationTrade"]
    ] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    arbitrages: Mapped[
        list["SimulationArbitrage"]
    ] = relationship(
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

    account: Mapped[
        "SimulationAccount"
    ] = relationship(
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

    account: Mapped[
        "SimulationAccount"
    ] = relationship(
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
        default=utc_now,
    )

    decision_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    account: Mapped[
        "SimulationAccount"
    ] = relationship(
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
        default=utc_now,
    )

    account: Mapped[
        "SimulationAccount"
    ] = relationship(
        back_populates="arbitrages",
    )


class SimulationBotCycle(Base):
    __tablename__ = "simulation_bot_cycles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_accounts.id"),
        index=True,
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
    )

    reason: Mapped[str] = mapped_column(
        Text,
    )

    evaluated_symbols_json: Mapped[str] = mapped_column(
        Text,
    )

    trade_candidates: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    best_symbol: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    best_profit_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )

    best_profit_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
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
        default=utc_now,
        onupdate=utc_now,
    )


class DecisionOrigin(str, Enum):
    TECHNICAL = "TECHNICAL"
    EXTERNAL = "EXTERNAL"


class DecisionStatus(str, Enum):
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    OPENED = "OPENED"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    STOPPED = "STOPPED"
    TAKE_PROFIT = "TAKE_PROFIT"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class BotPhaseName(str, Enum):
    SIMULATION = "SIMULATION"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class SignalDecision(Base):
    """Una fila por decisión (técnica o externa), con snapshot y resultado."""

    __tablename__ = "signal_decisions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    client_order_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    side: Mapped[TradeSide] = mapped_column(
        SqlEnum(TradeSide),
    )

    origin: Mapped[DecisionOrigin] = mapped_column(
        SqlEnum(DecisionOrigin),
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    config_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    market_snapshot_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    status: Mapped[DecisionStatus] = mapped_column(
        SqlEnum(DecisionStatus),
        default=DecisionStatus.PENDING,
        index=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    stop_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    take_profit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    fees_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )

    pnl_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class PositionV2(Base):
    """Posición de la fase 1: una por par, con stop/tp asociados (RF-12/RF-13)."""

    __tablename__ = "position_v2s"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_accounts.id"),
        index=True,
    )

    decision_id: Mapped[int] = mapped_column(
        ForeignKey("signal_decisions.id"),
        unique=True,
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

    stop_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    take_profit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    stop_order_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    tp_order_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[PositionStatus] = mapped_column(
        SqlEnum(PositionStatus),
        default=PositionStatus.OPEN,
    )

    entry_fee_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class TradeIncident(Base):
    """Incidencia registrada para el panel (RF-13 alerta, RF-24 slippage)."""

    __tablename__ = "trade_incidents"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(40),
        index=True,
    )

    symbol: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("signal_decisions.id"),
        nullable=True,
        index=True,
    )

    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("position_v2s.id"),
        nullable=True,
        index=True,
    )

    details: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        index=True,
    )


class DailyRiskState(Base):
    """Contador diario de riesgo: pérdida, aperturas y bloqueo (RF-4/RF-5)."""

    __tablename__ = "daily_risk_states"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    day: Mapped[date] = mapped_column(
        Date,
        unique=True,
        index=True,
    )

    start_equity_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )

    realized_pnl_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )

    opens_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    block_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class BotPhase(Base):
    """Fase activa del bot: SIMULATION → TESTNET → LIVE (RF-16)."""

    __tablename__ = "bot_phases"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    phase: Mapped[BotPhaseName] = mapped_column(
        SqlEnum(BotPhaseName),
        default=BotPhaseName.SIMULATION,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    evidence_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    changed_by: Mapped[str] = mapped_column(
        String(50),
        default="system",
    )


class BotRuntime(Base):
    """Única fila: kill switch y circuit breaker (RF-3/RF-22)."""

    __tablename__ = "bot_runtimes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    running: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    breaker_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    breaker_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class SystemEvent(Base):
    """Evento de observabilidad (spec 005, RF-3).

    Una fila por evento estructurado (ciclo, decisiA3n, orden, fuente). El
    ``correlation_id`` une todas las filas y la decisiA3n de un mismo ciclo
    (RF-2); los secretos se redactan antes de persistir (RF-4).
    """

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        index=True,
    )

    level: Mapped[str] = mapped_column(
        String(10),
    )

    service: Mapped[str] = mapped_column(
        String(50),
    )

    event: Mapped[str] = mapped_column(
        String(60),
        index=True,
    )

    asset: Mapped[str | None] = mapped_column(
        String(12),
        nullable=True,
    )

    correlation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    mode: Mapped[str] = mapped_column(
        String(20),
        default="unknown",
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    result: Mapped[str] = mapped_column(
        String(20),
    )

    payload_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )


class SourceHealth(Base):
    """Estado de salud de una fuente de datos (spec 005, RF-5).

    Estados: HEALTHY | DEGRADED | STALE | ERROR | DISABLED (D-6).
    """

    __tablename__ = "source_health"

    name: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    state: Mapped[str] = mapped_column(
        String(12),
        default="DISABLED",
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )


class AiEvaluation(Base):
    """Dictamen del analista IA (spec 007, RF-6).

    Una fila por consulta que llegó a Gemini (estado OK | ERROR); los
    cortes locales (DISABLED/cuota/presupuesto/breaker) solo dejan evento.
    El coste se guarda en USD como Decimal (nunca float).
    """

    __tablename__ = "ai_evaluations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    trigger: Mapped[str] = mapped_column(
        String(10),
        default="manual",
    )

    status: Mapped[str] = mapped_column(
        String(10),
        default="OK",
    )

    decision: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    direction: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )

    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    correlation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    prompt_version: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
    )

    context_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    response_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class HypothesisStatus(str, Enum):
    """Máquina de estados del aprendizaje (spec 010, §17)."""

    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    REJECTED = "REJECTED"


class Hypothesis(Base):
    """Hipótesis de aprendizaje (spec 010, RF-1): lo que el sistema sospecha."""

    __tablename__ = "hypotheses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    statement: Mapped[str] = mapped_column(
        Text,
    )

    origin_data_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    case_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    favorable_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    unfavorable_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 6),
        nullable=True,
    )

    observed_period_start: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    observed_period_finish: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    assets_json: Mapped[str] = mapped_column(
        Text,
        default="[]",
    )

    market_regime: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    status: Mapped[HypothesisStatus] = mapped_column(
        SqlEnum(HypothesisStatus),
        default=HypothesisStatus.PROPOSED,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    source: Mapped[str] = mapped_column(
        String(20),
        default="operator",
    )

    evaluation_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )
