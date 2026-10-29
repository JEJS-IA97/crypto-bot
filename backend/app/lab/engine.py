"""Cuentas virtuales del torneo: long y short en paper, contabilidad en Decimal.

Reglas comunes a todas las estrategias para que la comparación sea justa:
- comisión 0,10 % por lado y slippage 0,05 % en contra en entrada y salida;
- riesgo 2 % del equity por operación (distancia a stop), sin apalancamiento:
  el nominal nunca supera el efectivo libre (un short también inmoviliza su
  nominal como garantía);
- mínimo de Binance: una orden de menos de 5 USD no se abre (con 20 USD esto
  limita cuántas posiciones caben a la vez: es parte del experimento);
- una posición por símbolo y cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

FEE_RATE = Decimal("0.001")
SLIPPAGE = Decimal("0.0005")
RISK_PCT = Decimal("0.02")
STOPLESS_ALLOCATION = Decimal("0.25")
MIN_NOTIONAL = Decimal("5")
QTY_PLACES = Decimal("0.00000001")
CENT = Decimal("0.00000001")


def dec(value: float | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass
class Position:
    symbol: str
    side: str  # LONG | SHORT
    qty: Decimal
    entry: Decimal
    stop: Decimal | None
    take_profit: Decimal | None
    notional: Decimal
    entry_fee: Decimal
    opened_ts: int
    regime: str
    risk_usd: Decimal | None
    db_id: int | None = None

    def value(self, price: Decimal) -> Decimal:
        if self.side == "LONG":
            return self.qty * price
        return self.notional + self.qty * (self.entry - price)

    def hit(self, low: Decimal, high: Decimal) -> tuple[str, Decimal] | None:
        """¿Toca stop o TP en el rango [low, high]? Si ambos: stop (conservador)."""
        if self.side == "LONG":
            if self.stop is not None and low <= self.stop:
                return "stop", self.stop
            if self.take_profit is not None and high >= self.take_profit:
                return "tp", self.take_profit
        else:
            if self.stop is not None and high >= self.stop:
                return "stop", self.stop
            if self.take_profit is not None and low <= self.take_profit:
                return "tp", self.take_profit
        return None


@dataclass
class Trade:
    strategy: str
    capital: Decimal
    symbol: str
    side: str
    qty: Decimal
    entry: Decimal
    exit: Decimal
    opened_ts: int
    closed_ts: int
    pnl: Decimal
    fees: Decimal
    r_multiple: Decimal | None
    regime: str
    reason: str


@dataclass
class Account:
    strategy: str
    capital: Decimal
    cash: Decimal = field(default=Decimal(0))
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    skipped: int = 0
    fee_rate: Decimal = FEE_RATE  # spot 0,10 %; las de futuros simulan maker 0,02 %

    def __post_init__(self) -> None:
        if not self.cash:
            self.cash = self.capital

    def equity(self, prices: dict[str, Decimal] | None = None) -> Decimal:
        prices = prices or {}
        return self.cash + sum(
            (p.value(prices.get(s, p.entry)) for s, p in self.positions.items()),
            Decimal(0),
        )

    def open(
        self,
        *,
        symbol: str,
        side: str,
        price: Decimal,
        stop: Decimal | None,
        take_profit: Decimal | None,
        ts: int,
        regime: str,
        prices: dict[str, Decimal] | None = None,
    ) -> Position | None:
        if symbol in self.positions:
            return None
        entry = price * (1 + SLIPPAGE) if side == "LONG" else price * (1 - SLIPPAGE)
        if stop is not None:
            per_unit = abs(entry - stop)
            if per_unit <= 0 or (side == "LONG") != (stop < entry):
                return None
            qty = self.equity(prices) * RISK_PCT / per_unit
        else:
            per_unit = None
            # Sin stop: 25 % del equity, pero nunca menos del mínimo de
            # Binance (con 20 USD el 25 % no llega a 5 USD).
            budget = max(self.equity(prices) * STOPLESS_ALLOCATION, MIN_NOTIONAL * Decimal("1.01"))
            qty = budget / entry
        max_qty = self.cash / (entry * (1 + self.fee_rate))
        qty = min(qty, max_qty).quantize(QTY_PLACES, rounding=ROUND_DOWN)
        notional = qty * entry
        if notional < MIN_NOTIONAL:
            self.skipped += 1
            return None
        fee = notional * self.fee_rate
        self.cash -= notional + fee
        position = Position(
            symbol=symbol,
            side=side,
            qty=qty,
            entry=entry,
            stop=stop,
            take_profit=take_profit,
            notional=notional,
            entry_fee=fee,
            opened_ts=ts,
            regime=regime,
            risk_usd=qty * per_unit if per_unit is not None else None,
        )
        self.positions[symbol] = position
        return position

    def close(self, symbol: str, price: Decimal, ts: int, reason: str) -> Trade | None:
        position = self.positions.pop(symbol, None)
        if position is None:
            return None
        if position.side == "LONG":
            exit_price = price * (1 - SLIPPAGE)
            gross = position.qty * exit_price
        else:
            exit_price = price * (1 + SLIPPAGE)
            gross = position.notional + position.qty * (position.entry - exit_price)
        exit_fee = position.qty * exit_price * self.fee_rate
        proceeds = gross - exit_fee
        self.cash += proceeds
        pnl = proceeds - position.notional - position.entry_fee
        trade = Trade(
            strategy=self.strategy,
            capital=self.capital,
            symbol=symbol,
            side=position.side,
            qty=position.qty,
            entry=position.entry,
            exit=exit_price,
            opened_ts=position.opened_ts,
            closed_ts=ts,
            pnl=pnl.quantize(CENT),
            fees=(position.entry_fee + exit_fee).quantize(CENT),
            r_multiple=(
                (pnl / position.risk_usd).quantize(Decimal("0.01"))
                if position.risk_usd
                else None
            ),
            regime=position.regime,
            reason=reason,
        )
        self.trades.append(trade)
        return trade
