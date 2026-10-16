# Spec 012 — Estrategia ORB v2 con filtro de tendencia

> **Estado: NO VALIDADA — en reposo (2026-10-16).** ORB v1 no pasó su walk-forward (−14.1 % neto, 0/6 folds, PnL bruto negativo) y ORB v2 nunca se evaluó (T10 sin hacer). Por constitución #2 el código se conserva, pero el loop no evalúa ORB: `orb_enabled=False` por defecto en `app/config.py`. Reactivarlo exige spec nueva aprobada. Contexto: `docs/contexto-2026-10-16/README.md`.

## Contexto

La spec 011 construyó el walk-forward ORB y su gate estadístico. Ejecutado con datos
reales (365d, 5 pares, 5m), el veredicto fue **NO PASA**: -16.96 USD agregados,
0/6 folds ganadores, 15% de trades ganadores y 14.16 USD en comisiones. Diagnóstico:
ORB puro en 5m dispara demasiadas entradas (~60/mes) con margen insuficiente; los
rompimientos contra-tendencia son los que más stop tocan.

Esta spec define la v2 de la estrategia: **ORB + filtro de tendencia mayor**, el puente
métrico de simulación → testnet → real, y la subida de capital real acordada.

## Decisiones (ratificadas en entrevista 2026-10-10)

- D-1: Filtro = precio de la vela de rompimiento ≥ EMA(50) sobre velas 1h del mismo
  símbolo. Determinista, sin librerías nuevas, calculable con datos ya disponibles.
- D-2: Alcance de exchange: **solo Binance Spot** (constitución sin enmienda).
  BingX y OKX quedan fuera.
- D-3: Puente a real por gate numérico: SIMULATION→TESTNET exige walk-forward v2 PASA;
  TESTNET→LIVE exige ≥30 trades en paper con expectancy ≥ 0 y drawdown ≤ 5%.
- D-4: Capital real sube de 20 a **40 USD** (tope del rango 30-40 pedido). Pérdida
  máxima por operación 1 USD; pérdida máxima diaria 5% del capital (2 USD).
- D-5: Los pares ORB se mantienen: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT.
- D-6: Un solo código de decisión para backtest, paper y real (sin divergencias).

## Resoluciones de clarificación (QA 2026-10-10, decisión del propietario delegada)

- D-7: **Fail-closed sin datos 1h**: si un símbolo no dispone de ≥50 velas 1h
  cerradas, no se emite señal para él (consistente con RNF-6 de la constitución).
- D-8: El walk-forward v2 consume las velas 1h de `data/klines_1h/`, descargadas
  con el mismo `collect_klines.py --interval 1h`.
- D-9: La cuenta de paper se **resetea a 40 USD** al implementar el capital nuevo,
  para que sizing y pérdida diaria coincidan con el capital real configurado.
- D-10: Los gates de fase (RF-4/RF-5) se **verifican automáticamente** en el
  cambio de fase: walk-forward v2 con veredicto PASA persistido en BD y métricas
  de paper leídas de la BD. Sin evidencia manual.
- D-11: El gate RF-5 exige ≥30 trades de paper **sin plazo mínimo de días**
  (alcanzable en ~1-2 meses con 5 pares); no se relaja el umbral.
- D-12: EMA exponencial estándar α=2/(n+1), semilla = media aritmética de las
  primeras n velas; en el filtro solo entran velas 1h **completamente cerradas**
  (evita look-ahead y deriva live/backtest).

## Requisitos funcionales (EARS)

- **RF-1**: Mientras el motor ORB emita BUY por rompimiento, el sistema SHALL emitir
  BUY solo si además el precio de cierre de la vela de rompimiento es ≥ EMA(50)
  calculada sobre las 50 velas 1h cerradas inmediatamente antes de dicha vela.
  Si no se cumple, la decisión SHALL ser HOLD con motivo `trend_filter_reject`.
- **RF-2**: El ciclo del bot y el pipeline walk-forward SHALL disponer de klines 1h
  por símbolo (mínimo 55 velas previas) para calcular la EMA del filtro. Si un
  símbolo no dispone de ≥50 velas 1h cerradas, el sistema SHALL abstenerse de
  emitir señal para ese símbolo (fail-closed, D-7).
- **RF-3**: El walk-forward de la spec 011 SHALL evaluar la v2 con el mismo CLI,
  métricas y gate (PnL agregado out-of-sample > 0 tras costes) que la v1.
- **RF-4**: El cambio de fase SIMULATION→TESTNET SHALL exigir, además de los
  blockers actuales, evidencia de walk-forward v2 con veredicto PASA.
- **RF-5**: El cambio de fase TESTNET→LIVE SHALL exigir, además de los blockers
  actuales, evidencia de ≥30 trades de paper con expectancy ≥ 0 y máximo
  drawdown ≤ 5% del capital aportado.
- **RF-6**: El capital aportado configurado SHALL ser 40 USD; el risk engine SHALL
  mantener pérdida máxima 1 USD por operación y bloqueo diario a las pérdidas ≥ 5%
  del capital (2 USD). `ALLOW_LIVE_TRADING=true` seguirá siendo la llave maestra.
- **RF-7**: paper (simulación), backtest y real SHALL usar la misma función de
  decisión con filtro; no SHALL existir lógica duplicada de señales.
- **RF-8**: Sin dependencias nuevas; todo cálculo monetario en Decimal.

## Fuera de alcance

- Modelos ML de predicción sube/baja/lateral (spec futura).
- Exchanges distintos de Binance Spot (OKX demo existente se queda como está).
- Cambios de UI/panel (los endpoints de fase y decisiones ya existen).
- Estrategias de salida nuevas (stop 2% / take-profit se mantienen).
- El bot de arbitraje entre exchanges (código no cableado, se ignora).

## Criterios de finalización

1. Walk-forward v2 ejecutado con datos reales 365d y veredicto mostrado (PASA o
   NO PASA documentado; NO PASA ⇒ se iteran filtros/parámetros y se re-ejecuta).
2. Tests de cada RF verdes; suite completa sin regresiones.
3. `configured_capital_usd` = 40 USD y constitución actualizada (puntos de capital).
4. Fase del bot actualizable a TESTNET cuando el walk-forward v2 dé PASA.
