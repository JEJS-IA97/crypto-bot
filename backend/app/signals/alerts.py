"""Avisos de compra/venta a tu Telegram (Mensajes guardados), para operar a mano.

Solo avisan las estrategias que aprobaron el examen del cerebro (evo_*): las demás aún
no demostraron nada. El lector de Telegram vacía esta cola cada ~15 s.
"""

from __future__ import annotations

from decimal import Decimal

outbox: list[str] = []


def _p(x: Decimal | None) -> str:
    return "—" if x is None else f"{float(x):,.4f}".rstrip("0").rstrip(".")


def on_open(strategy, symbol: str, position) -> None:
    if not strategy.name.startswith("evo_"):
        return
    side = "COMPRA" if position.side == "LONG" else "VENTA"
    outbox.append(
        f"{'🟢' if side == 'COMPRA' else '🔴'} {side} {symbol.replace('USDT', '')} a {_p(position.entry)}\n"
        f"Estrategia: {strategy.label}\nStop: {_p(position.stop)} · Objetivo: {_p(position.take_profit)}\n"
        "Señal del bot en paper. Si operas a mano, decides tú el tamaño."
    )


def on_close(strategy_name: str, label: str, symbol: str, trade) -> None:
    if not strategy_name.startswith("evo_") or trade is None:
        return
    outbox.append(
        f"⚪ CERRAR {symbol.replace('USDT', '')} a {_p(trade.exit)} ({trade.reason})\n"
        f"Estrategia: {label} · resultado en paper {float(trade.pnl):+.2f} USD"
    )
