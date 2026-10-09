"""Loop autónomo del bot (spec 001, módulo M8).

Flujo por ciclo (plan §Algoritmo / flujo principal):

1. ``bot_runtime``: breaker (RF-22) o ``running=false`` (kill switch,
   RF-3) → el ciclo no opera.
2. Descarga de klines 15m + exchangeInfo de todos los pares; en la ventana
   ORB (9:00–10:00 AM NY) además klines 5m de los pares ORB sin decisión
   técnica hoy (RF-6/RF-27). Cualquier fallo propaga
   ``MarketDataUnavailable`` → ciclo fallido, sin órdenes (RNF-6,
   fail-closed) y se cuenta para el breaker.
3. Para cada par: reconciliar stop/tp de posiciones abiertas (M6),
   señales externas en cola (M3), señal ORB (M2), conflicto → gana la
   externa (RF-23), riesgo (M5), orden idempotente (M7, RF-25) y
   persistencia (M9/M6, RF-10/RF-13). La técnica nunca emite SELL (RF-7).

El kill switch se revisa antes de cada par y otra vez justo antes de cada
orden: detener no reinicia el loop, solo lo deja dormido (``controller``.
notify() lo despierta al instante desde la API, que corre en otro hilo →
RNF-3: la API responde mientras el loop evalúa).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import database
from app.config import settings
from app.domain.orb_engine import (
    OrbConfig,
    evaluate_orb,
    in_orb_window,
    ny_day_start_utc,
)
from app.domain.risk_math import calculate_order_size
from app.domain.signal_engine import (
    Candle,
    SignalAction,
    SignalResult,
)
from app.models import (
    BotRuntime,
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
    utc_now,
)
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
    SymbolRules,
)
from app.services.decision_store import (
    has_technical_decision_since,
    mark_rejected,
    record_decision,
)
from app.services.exchange_executor import ExchangeExecutor, OrderRequest
from app.services.external_signal_service import (
    EXTERNAL_CONFLICT_REASON,
    resolve_signal_conflict,
)
from app.services.observability_service import mark_source, purge_old_events
from app.services.order_lifecycle import (
    check_exits,
    close_position,
    protection_after_fill,
)
from app.services.phase_service import get_phase
from app.services.risk_engine_service import (
    RiskAction,
    evaluate_open,
)
from app.services.risk_guard_service import (
    get_daily_state,
    get_runtime,
    record_cycle_failure,
    record_cycle_success,
    record_realized_pnl,
    register_open,
)
from app.services.simulation_executor import SimulationExecutor
from app.services.simulation_service import get_balance_record
from app.services.structured_log import emit

logger = logging.getLogger(__name__)

MarketData = BinanceMarketDataClient
CycleRunner = Callable[..., "CycleReport"]

REASON_KILL_SWITCH = "kill_switch"
REASON_EXPIRED = "signal_expired"
REASON_NO_POSITION = "no_position_to_close"
REASON_POSITION_OPEN = "position_already_open"
REASON_SUPERSEDED = "superseded_by_external_signal"
REASON_NOT_TRADING = "symbol_not_trading"
REASON_NON_ORB = "non_orb_symbol"
REASON_ORB_SKIPPED = "orb_not_evaluated"

# Velas 5m para la ventana ORB (6 del rango + 6 del rompimiento, con
# margen para reinicios y caché): 50 velas = ~4 h de historial.
ORB_KLINE_LIMIT = 50

# Spec 005, RF-8: purga de eventos viejos como máximo una vez cada 24 h
# (además de la purga al arrancar en el lifespan de main).
PURGE_INTERVAL_SECONDS = 86400


@dataclass(frozen=True)
class CycleReport:
    """Resultado de un ciclo: ok (operó), stopped, breaker o failed."""

    status: str
    opened: int = 0
    closed: int = 0
    rejected: int = 0
    error: str = ""


def _mark_source_quiet(
    db: Session, name: str, *, ok: bool, error: str = ""
) -> None:
    """Marca la salud de una fuente sin romper el ciclo (spec 005, RF-5)."""
    try:
        mark_source(db, name, ok=ok, error=error)
    except Exception:
        logger.exception("could not mark source %s", name)


def _current_mode(db: Session) -> str:
    """Fase activa para el campo ``mode`` de los eventos (spec 005, RF-1)."""
    try:
        return get_phase(db).phase.value
    except Exception:
        logger.exception("could not resolve current phase")
        return "unknown"


class BotLoopController:
    """Coordina la pausa del loop con la API (RF-3, RNF-3).

    ``notify()`` es seguro desde cualquier hilo: la ruta de la API corre en
    el hilo de la API y el loop en el hilo de asyncio.
    """

    def __init__(self) -> None:
        self._event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _arm(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._event = asyncio.Event()

    def _disarm(self) -> None:
        self._event = None
        self._loop = None

    def notify(self) -> None:
        event = self._event
        if event is None:
            return
        loop = self._loop
        if loop is None:
            event.set()
        else:
            loop.call_soon_threadsafe(event.set)

    async def sleep(self, seconds: float) -> None:
        """Duerme hasta el próximo ciclo; ``notify()`` lo despierta ya."""
        event = self._event
        if event is None:
            await asyncio.sleep(seconds)
            return
        try:
            await asyncio.wait_for(event.wait(), timeout=seconds)
        except TimeoutError:
            pass
        event.clear()


controller = BotLoopController()


def _trading_symbols() -> list[str]:
    return [
        part.strip().upper()
        for part in settings.trading_symbols.split(",")
        if part.strip()
    ]


def _orb_symbols() -> set[str]:
    """Pares con señal técnica ORB (spec 001, D-12)."""
    return {
        part.strip().upper()
        for part in settings.orb_symbols.split(",")
        if part.strip()
    }


def _is_running(db: Session) -> bool:
    """Kill switch leído del registro persistido (visible entre hilos)."""
    value = db.execute(
        select(BotRuntime.running).where(BotRuntime.id == 1)
    ).scalar_one_or_none()
    if value is None:
        return True
    return bool(value)


def _snapshot(
    *,
    candles: list[Candle],
    price: Decimal,
    result: SignalResult | None,
    now: datetime,
) -> dict:
    """Snapshot de mercado de la decisión: precio + velas + indicadores."""
    return {
        "price": price,
        "timestamp": now.isoformat(),
        "indicators": dict(result.metrics) if result is not None else {},
        "candles": [
            {
                "open_time": candle.open_time.isoformat(),
                "open": str(candle.open),
                "high": str(candle.high),
                "low": str(candle.low),
                "close": str(candle.close),
                "volume": str(candle.volume),
            }
            for candle in candles[-3:]
        ],
    }


def _record_close_pnl(db: Session, state, decision: SignalDecision) -> None:
    if decision.pnl_usd is not None:
        record_realized_pnl(db, state, decision.pnl_usd)


def _mark_external_closed(
    db: Session,
    decision: SignalDecision,
    now: datetime,
) -> None:
    """La externa que ejecutó un cierre queda cerrada sin PnL propio.

    El resultado (PnL/comisiones) vive en la decisión de la posición
    abierta (RF-10): aquí no se duplica para no sumarlo dos veces.
    """
    decision.status = DecisionStatus.CLOSED
    decision.closed_at = now
    db.commit()


def _try_open(
    db: Session,
    *,
    symbol: str,
    candles: list[Candle],
    candles_by_symbol: dict[str, list[Candle]],
    price: Decimal,
    rules: SymbolRules,
    state,
    balance,
    executor: ExchangeExecutor,
    orb_config: OrbConfig,
    now: datetime,
    account_id: int,
    decision: SignalDecision | None = None,
    technical: SignalResult | None = None,
    correlation_id: str | None = None,
) -> str:
    """Riesgo → orden idempotente → stop/tp. Devuelve opened/rejected/stopped."""
    if decision is None:
        decision = record_decision(
            db,
            symbol=symbol,
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config=asdict(orb_config),
            snapshot={
                **_snapshot(
                    candles=candles,
                    price=price,
                    result=technical,
                    now=now,
                ),
                # Spec 005, RF-2: el correlation_id del ciclo.
                "correlation_id": correlation_id,
            },
            price=price,
        )

    if not rules.tradable:
        mark_rejected(db, decision, REASON_NOT_TRADING)
        return "rejected"

    quantity = decision.quantity
    if quantity is None:
        sizing = calculate_order_size(
            price=price,
            capital_usd=settings.configured_capital_usd,
            available_usd=balance.available_usd,
            min_notional_usd=rules.min_notional,
            step_size=rules.step_size,
            stop_loss_pct=settings.stop_loss_pct,
        )
        if sizing.discarded:
            mark_rejected(db, decision, sizing.reason)
            return "rejected"
        quantity = sizing.quantity
    decision.quantity = quantity

    # Spec 008, D-1: el motor envuelve risk_guard y añade los topes de
    # posiciones/exposición y el resize por correlación (RF-1/RF-2).
    assessment = evaluate_open(
        db,
        symbol=symbol,
        now=now,
        state=state,
        account_id=account_id,
        quantity=quantity,
        price=price,
        candles=candles_by_symbol.get(symbol, candles),
        other_candles=candles_by_symbol,
        step_size=rules.step_size,
        min_notional_usd=rules.min_notional,
        available_usd=balance.available_usd,
        correlation_id=correlation_id,
    )
    if assessment.action == RiskAction.BLOCKED:
        mark_rejected(db, decision, assessment.reason)
        return "rejected"
    if assessment.action == RiskAction.RESIZED:
        # RF-1: la orden usa la cantidad redimensionada (D-3).
        quantity = assessment.allowed_quantity
        decision.quantity = quantity

    if not _is_running(db):
        # RF-3: ni una orden nueva. La externa queda en cola (PENDING) para
        # el próximo ciclo; la técnica se descarta con motivo visible.
        if decision.origin == DecisionOrigin.TECHNICAL:
            mark_rejected(db, decision, REASON_KILL_SWITCH)
        return "stopped"

    # Spec 005, RF-1: traza de la orden enviada (auditable, sin secretos).
    emit(
        service="bot_loop",
        event="order.sent",
        result="ok",
        asset=symbol,
        correlation_id=correlation_id,
        payload={
            "decision_id": decision.id,
            "client_order_id": decision.client_order_id,
            "quantity": str(quantity),
            "price": str(price),
        },
        db=db,
    )
    try:
        fill = executor.place_order(
            OrderRequest(
                symbol=symbol,
                side="BUY",
                order_type="LIMIT",
                quantity=quantity,
                price=price,
                client_order_id=decision.client_order_id,
            )
        )
    except ValueError as exc:
        reason_text = getattr(exc, "reason", None) or str(exc)
        emit(
            service="bot_loop",
            event="order.failed",
            level="WARNING",
            result="failed",
            asset=symbol,
            correlation_id=correlation_id,
            payload={
                "decision_id": decision.id,
                "reason": reason_text,
            },
            db=db,
        )
        mark_rejected(db, decision, reason_text)
        return "rejected"

    position = PositionV2(
        account_id=account_id,
        decision_id=decision.id,
        symbol=symbol,
        quantity=fill.executed_quantity,
        average_entry_price=fill.average_price,
        entry_fee_usd=(
            fill.fee if fill.fee is not None else Decimal("0")
        ),
    )
    db.add(position)
    db.commit()
    position = protection_after_fill(
        db,
        position=position,
        decision=decision,
        fill=fill,
        tick_size=rules.tick_size,
    )
    if position.status == PositionStatus.OPEN:
        register_open(db, state, symbol)
        emit(
            service="bot_loop",
            event="order.filled",
            result="ok",
            asset=symbol,
            correlation_id=correlation_id,
            payload={
                "decision_id": decision.id,
                "position_id": position.id,
                "quantity": str(fill.executed_quantity),
                "price": str(fill.average_price),
            },
            db=db,
        )
        return "opened"
    emit(
        service="bot_loop",
        event="order.failed",
        level="WARNING",
        result="failed",
        asset=symbol,
        correlation_id=correlation_id,
        payload={
            "decision_id": decision.id,
            "position_id": position.id,
            "status": position.status.value,
        },
        db=db,
    )
    return "rejected"


def _execute_cycle(
    db: Session,
    *,
    market_data: MarketData,
    symbols: list[str],
    account_id: int,
    orb_config: OrbConfig,
    executor: ExchangeExecutor | None,
    now: datetime,
    correlation_id: str | None = None,
) -> CycleReport:
    runtime = get_runtime(db)
    if runtime.breaker_active:
        return CycleReport(
            status="breaker",
            error=runtime.breaker_reason or "breaker_active",
        )
    if not runtime.running:
        return CycleReport(status="stopped")

    # RNF-6: cualquier fallo de datos aborta el ciclo sin operar.
    candles_by_symbol: dict[str, list[Candle]] = {}
    rules_by_symbol: dict[str, SymbolRules] = {}
    for symbol in symbols:
        candles = market_data.get_klines(symbol)
        if not candles:
            raise MarketDataUnavailable(
                f"Empty klines for {symbol}"
            )
        rules = market_data.get_exchange_info(symbol)
        candles_by_symbol[symbol] = candles
        rules_by_symbol[symbol] = rules

    # Spec 005, RF-5: las fuentes públicas respondieron (los fallos salen
    # desde run_once y se marcan ERROR).
    _mark_source_quiet(db, "binance_klines", ok=True)
    _mark_source_quiet(db, "binance_exchange_info", ok=True)

    # RF-6: en la ventana ORB (9:00–10:00 AM NY) descarga además 5m para
    # los pares ORB sin decisión técnica hoy (RF-27: sin dedup no hay
    # evaluación, así que tampoco descarga).
    active_orb_symbols = _orb_symbols()
    orb_symbols = [
        symbol for symbol in symbols if symbol in active_orb_symbols
    ]
    orb_candles_by_symbol: dict[str, list[Candle]] = {}
    if orb_symbols and in_orb_window(now, orb_config):
        since = ny_day_start_utc(now, orb_config)
        for symbol in orb_symbols:
            if has_technical_decision_since(
                db, symbol=symbol, since=since
            ):
                continue
            candles_5m = market_data.get_klines(
                symbol, interval="5m", limit=ORB_KLINE_LIMIT
            )
            if not candles_5m:
                raise MarketDataUnavailable(
                    f"Empty ORB klines for {symbol}"
                )
            orb_candles_by_symbol[symbol] = candles_5m

    active_executor = (
        executor
        if executor is not None
        else SimulationExecutor(db, account_id)
    )
    balance = get_balance_record(db, account_id)
    state = get_daily_state(
        db,
        now.date(),
        balance.available_usd + balance.invested_usd,
    )

    open_positions = {
        position.symbol: position
        for position in db.scalars(
            select(PositionV2).where(
                PositionV2.account_id == account_id,
                PositionV2.status == PositionStatus.OPEN,
            )
        ).all()
    }
    pending_external = {
        decision.symbol: decision
        for decision in db.scalars(
            select(SignalDecision).where(
                SignalDecision.status == DecisionStatus.PENDING,
                SignalDecision.origin == DecisionOrigin.EXTERNAL,
            )
        ).all()
    }

    opened = 0
    closed = 0
    rejected = 0
    stopped = False

    for symbol in symbols:
        if not _is_running(db):
            stopped = True
            break
        candles = candles_by_symbol[symbol]
        price = candles[-1].close
        rules = rules_by_symbol[symbol]
        position = open_positions.get(symbol)
        external = pending_external.get(symbol)

        if position is not None:
            decision = db.get(SignalDecision, position.decision_id)
            if external is not None:
                if external.side == TradeSide.SELL:
                    close_position(
                        db,
                        position=position,
                        decision=decision,
                        executor=active_executor,
                        exit_price=price,
                        expected_price=price,
                        reason="manual",
                    )
                    closed += 1
                    _record_close_pnl(db, state, decision)
                    _mark_external_closed(db, external, now)
                    continue
                mark_rejected(db, external, REASON_POSITION_OPEN)
                rejected += 1
                continue

            closed_position = check_exits(
                db,
                position=position,
                decision=decision,
                executor=active_executor,
                current_price=price,
            )
            if closed_position is not None:
                closed += 1
                _record_close_pnl(db, state, decision)
            # RF-7 v3: la señal técnica nunca emite SELL. Las posiciones
            # se cierran por stop/tp (RF-13) o externa (RF-8).
            continue

        orb_candles = orb_candles_by_symbol.get(symbol)
        if orb_candles is not None:
            technical = evaluate_orb(orb_candles, now, orb_config)
        elif symbol not in active_orb_symbols:
            technical = SignalResult(
                SignalAction.HOLD, REASON_NON_ORB, {}
            )
        else:
            # Fuera de ventana o día NY ya agotado (RF-27): sin emitir.
            technical = SignalResult(
                SignalAction.HOLD, REASON_ORB_SKIPPED, {}
            )
        # Snapshot de la decisión técnica: las velas con las que se evaluó.
        decision_candles = orb_candles if orb_candles is not None else candles

        if external is not None:
            age_seconds = (now - external.created_at).total_seconds()
            if age_seconds > settings.signal_ttl_seconds:
                mark_rejected(db, external, REASON_EXPIRED)
                rejected += 1
                external = None

        if external is not None:
            if technical.action != SignalAction.HOLD:
                resolution = resolve_signal_conflict(
                    technical_symbol=symbol,
                    technical_action=technical.action,
                    external_symbol=external.symbol,
                    external_side=external.side,
                )
                conflict_reason = (
                    EXTERNAL_CONFLICT_REASON
                    if resolution.external_wins
                    else REASON_SUPERSEDED
                )
                side = (
                    TradeSide.BUY
                    if technical.action == SignalAction.BUY
                    else TradeSide.SELL
                )
                technical_decision = record_decision(
                    db,
                    symbol=symbol,
                    side=side,
                    origin=DecisionOrigin.TECHNICAL,
                    config=asdict(orb_config),
                    snapshot={
                        **_snapshot(
                            candles=decision_candles,
                            price=price,
                            result=technical,
                            now=now,
                        ),
                        # Spec 005, RF-2: el correlation_id del ciclo.
                        "correlation_id": correlation_id,
                    },
                    price=price,
                )
                mark_rejected(db, technical_decision, conflict_reason)
                rejected += 1

            # RF-23: gana la externa → la técnica no se ejecuta.
            if external.side == TradeSide.BUY:
                outcome = _try_open(
                    db,
                    symbol=symbol,
                    candles=candles,
                    candles_by_symbol=candles_by_symbol,
                    price=price,
                    rules=rules,
                    state=state,
                    balance=balance,
                    executor=active_executor,
                    orb_config=orb_config,
                    now=now,
                    account_id=account_id,
                    decision=external,
                    correlation_id=correlation_id,
                )
                if outcome == "opened":
                    opened += 1
                elif outcome == "rejected":
                    rejected += 1
                else:
                    stopped = True
            else:
                mark_rejected(db, external, REASON_NO_POSITION)
                rejected += 1
            continue

        if technical.action == SignalAction.BUY:
            outcome = _try_open(
                db,
                symbol=symbol,
                candles=decision_candles,
                candles_by_symbol=candles_by_symbol,
                price=price,
                rules=rules,
                state=state,
                balance=balance,
                executor=active_executor,
                orb_config=orb_config,
                now=now,
                account_id=account_id,
                technical=technical,
                correlation_id=correlation_id,
            )
            if outcome == "opened":
                opened += 1
            elif outcome == "rejected":
                rejected += 1
            else:
                stopped = True

    if stopped:
        return CycleReport(
            status="stopped",
            opened=opened,
            closed=closed,
            rejected=rejected,
        )
    return CycleReport(
        status="ok",
        opened=opened,
        closed=closed,
        rejected=rejected,
    )


def run_once(
    db: Session,
    *,
    market_data: MarketData,
    symbols: list[str] | None = None,
    account_id: int | None = None,
    orb_config: OrbConfig | None = None,
    executor: ExchangeExecutor | None = None,
    now: datetime | None = None,
) -> CycleReport:
    """Un ciclo completo con la contabilidad de fallos del breaker (RF-22)."""
    started_at = time.monotonic()
    # Spec 005, RF-2: un correlation_id por ciclo para unir eventos y
    # decisiones; viaja en el snapshot de cada decisión que emite el ciclo.
    correlation_id = str(uuid.uuid4())
    active_symbols = (
        list(symbols) if symbols is not None else _trading_symbols()
    )
    active_account = (
        account_id
        if account_id is not None
        else settings.simulation_bot_account_id
    )
    active_orb_config = orb_config if orb_config is not None else OrbConfig()
    active_now = now if now is not None else utc_now()

    try:
        report = _execute_cycle(
            db,
            market_data=market_data,
            symbols=active_symbols,
            account_id=active_account,
            orb_config=active_orb_config,
            executor=executor,
            now=active_now,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.exception("bot cycle failed")
        report = CycleReport(status="failed", error=str(exc))
        # Spec 005, RF-5: el fallo marca la fuente implicada (fail-open).
        if isinstance(exc, MarketDataUnavailable):
            _mark_source_quiet(db, "binance_klines", ok=False, error=str(exc))
        else:
            _mark_source_quiet(db, "database", ok=False, error=str(exc))

    if report.status == "failed":
        try:
            record_cycle_failure(db)
        except Exception:
            logger.exception("could not record cycle failure")
    elif report.status == "ok":
        record_cycle_success(db)
        _mark_source_quiet(db, "database", ok=True)

    emit(
        service="bot_loop",
        event="cycle.completed",
        level="ERROR" if report.status == "failed" else "INFO",
        result=report.status,
        correlation_id=correlation_id,
        latency_ms=int((time.monotonic() - started_at) * 1000),
        mode=_current_mode(db),
        payload={
            "opened": report.opened,
            "closed": report.closed,
            "rejected": report.rejected,
            "error": report.error,
        },
        db=db,
    )
    return report


async def run(
    *,
    stop_event: asyncio.Event | None = None,
    session_factory: Callable[[], Session] | None = None,
    cycle_runner: CycleRunner | None = None,
    market_data: MarketData | None = None,
    symbols: list[str] | None = None,
    account_id: int | None = None,
    orb_config: OrbConfig | None = None,
    interval_seconds: int | None = None,
) -> None:
    """Loop continuo (Decisión 7): una sola tarea asyncio en el proceso."""
    factory = (
        session_factory
        if session_factory is not None
        else database.SessionLocal
    )
    runner = cycle_runner if cycle_runner is not None else run_once
    data = (
        market_data
        if market_data is not None
        else BinanceMarketDataClient()
    )
    active_symbols = (
        list(symbols) if symbols is not None else _trading_symbols()
    )
    active_account = (
        account_id
        if account_id is not None
        else settings.simulation_bot_account_id
    )
    active_orb_config = orb_config if orb_config is not None else OrbConfig()
    interval = (
        interval_seconds
        if interval_seconds is not None
        else settings.trading_interval_seconds
    )

    controller._arm()
    last_purge = time.monotonic()
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            db = factory()
            try:
                runtime = get_runtime(db)
                if runtime.running and not runtime.breaker_active:
                    runner(
                        db,
                        market_data=data,
                        symbols=active_symbols,
                        account_id=active_account,
                        orb_config=active_orb_config,
                    )
            except Exception:
                logger.exception("bot loop cycle failed")
                try:
                    record_cycle_failure(db)
                except Exception:
                    logger.exception("could not record cycle failure")
            finally:
                # Spec 005, RF-8: purga por edad sin penalizar al breaker
                # (un fallo aquí nunca cuenta como ciclo fallido).
                if (
                    time.monotonic() - last_purge
                    >= PURGE_INTERVAL_SECONDS
                ):
                    try:
                        purge_old_events(db)
                        last_purge = time.monotonic()
                    except Exception:
                        logger.exception("could not purge old events")
                db.close()
            await controller.sleep(interval)
    finally:
        controller._disarm()
