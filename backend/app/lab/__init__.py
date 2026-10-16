"""Laboratorio de trading: torneo de estrategias en paper (longs y shorts).

Cada estrategia opera en paralelo en cuentas virtuales de 20, 50 y 100 USD
con comisión, slippage, stop y take-profit. El mismo código sirve para el
backtest histórico y para el modo en vivo (WebSocket de Binance). No toca
el bot principal ni dinero real.
"""
