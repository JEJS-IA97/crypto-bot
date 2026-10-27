"""Avisos de compra/venta a tu Telegram (Mensajes guardados), para operar a mano.

Solo avisa la cuenta principal: copia únicamente las fuentes con ventaja comprobada
en vivo (ver `live.champions`). El lector de Telegram vacía esta cola cada ~15 s.
"""

from __future__ import annotations

from decimal import Decimal

outbox: list[str] = []


def _p(x: Decimal | None) -> str:
    return "—" if x is None else f"{float(x):,.4f}".rstrip("0").rstrip(".")


def on_open(strategy, symbol: str, position) -> None:
    if strategy.name != "principal":
        return
    side = "COMPRA" if position.side == "LONG" else "VENTA"
    outbox.append(
        f"{'🟢' if side == 'COMPRA' else '🔴'} {side} {symbol.replace('USDT', '')} a {_p(position.entry)}\n"
        f"Copia de: {position.regime}\nStop: {_p(position.stop)} · Objetivo: {_p(position.take_profit)}\n"
        "Señal del bot en paper. Si operas a mano, decides tú el tamaño."
    )


def on_close(strategy_name: str, label: str, symbol: str, trade) -> None:
    if strategy_name != "principal" or trade is None:
        return
    outbox.append(
        f"⚪ CERRAR {symbol.replace('USDT', '')} a {_p(trade.exit)} ({trade.reason})\n"
        f"Estrategia: {label} · resultado en paper {float(trade.pnl):+.2f} USD"
    )
