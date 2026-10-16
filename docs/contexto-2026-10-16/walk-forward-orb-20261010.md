# Walk-forward ORB — reporte de evidencia

- Símbolos: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT
- Intervalo: 5m
- Ventanas: train 180 d / test 30 d / paso 30 d
- Costes: comisión 0.0010 por lado, slippage 0.05 % por lado
- Capital por ventana: 20 USD

## Folds

| # | Train | Test | SL | TP | Trades train | PnL validación | Trades test | PnL neto | Sharpe | PF | Expectancy |
|---|-------|------|----|----|--------------|-----------------|------------|----------|--------|----|-------------|
| 0 | 2025-10-10 → 2026-04-08 | 2026-04-08 → 2026-05-08 | 1.0 | 2.0 | 386 | -2.93551631 | 49 | -1.98544676 | -6.2196 | 0.2675 | -0.04051932 |
| 1 | 2025-11-09 → 2026-05-08 | 2026-05-08 → 2026-06-07 | 1.0 | 1.0 | 372 | -1.79576621 | 29 | -2.00157860 | -10.3148 | 0.0000 | -0.06901995 |
| 2 | 2025-12-09 → 2026-06-07 | 2026-06-07 → 2026-07-07 | 1.0 | 1.0 | 339 | -1.76064934 | 68 | -0.82841302 | -1.6672 | 0.7240 | -0.01218254 |
| 3 | 2026-01-08 → 2026-07-07 | 2026-07-07 → 2026-08-06 | 1.0 | 1.0 | 345 | -0.68384618 | 72 | -4.14078716 | -13.7797 | 0.1297 | -0.05751093 |
| 4 | 2026-02-07 → 2026-08-06 | 2026-08-06 → 2026-09-05 | 1.0 | 1.5 | 352 | -3.61923548 | 69 | -4.73583412 | -12.7206 | 0.0648 | -0.06863528 |
| 5 | 2026-03-09 → 2026-09-05 | 2026-09-05 → 2026-10-05 | 1.0 | 1.0 | 355 | -4.43556311 | 67 | -3.27130453 | -5.5852 | 0.3133 | -0.04882544 |

## Agregado out-of-sample

- PnL neto total (suma de tests): -16.96336419 USD
- Retorno neto: -14.14 %
- Máx. drawdown: 4.78974394 USD (23.88 %)
- Sharpe: -7.1055
- Profit factor: 0.2393
- Expectancy: -0.04791911 USD
- Trades: 354 (ganadores: 54)
- Comisiones: 14.15719383 USD

## Buy & hold (informativo, no forma parte del gate)

- ADAUSDT: -0.30337505 USD sobre 20 USD
- BNBUSDT: 5.65323959 USD sobre 20 USD
- BTCUSDT: 4.06878114 USD sobre 20 USD
- ETHUSDT: 4.33181944 USD sobre 20 USD
- SOLUSDT: 8.42449743 USD sobre 20 USD

## Veredicto

**NO PASA** — gate: PnL neto agregado out-of-sample > 0 tras costes (D-7).
