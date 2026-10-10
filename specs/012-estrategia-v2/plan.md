# Plan — spec 012: estrategia ORB v2 con filtro de tendencia

## Arquitectura de la solución

Punto único de integración del filtro: nuevo módulo de dominio puro
`app/domain/trend_filter.py`, consumido tanto por el motor ORB en vivo
(`orb_engine.evaluate_orb`, que gana un parámetro opcional `hourly_candles`)
como por el backtest (`strategy_lab_service.backtest_orb`, idem). El ORB
propio no se toca: el filtro es una compuerta anterior a BUY (D-6, RF-7).

## Módulos

| Módulo | Cambio | RF |
|--------|--------|----|
| `app/domain/trend_filter.py` (nuevo) | `compute_ema(candles, period)` (α=2/(n+1), semilla SMA, D-12) y `trend_allows(close, hourly_candles) -> tuple[bool, dict]`; solo velas 1h cerradas; <50 velas ⇒ False (fail-closed D-7). Sin floats, todo Decimal. | RF-1, RF-2, RF-8 |
| `app/domain/orb_engine.py` | `evaluate_orb(..., hourly_candles=None)`: si la acción es BUY y el filtro no permite ⇒ `HOLD("trend_filter_reject")` con métricas ema50/close en `result.metrics` (llegan al snapshot de decisión, constitución 10). | RF-1 |
| `app/services/strategy_lab_service.py` | `OrbBacktestConfig` gana `hourly_candles`; `backtest_orb` consulta `trend_allows` en el punto de entrada (cierre de la vela de rompimiento); sin hourly o filtro en falso ⇒ sin entrada ese día. | RF-3, RF-7 |
| `app/services/walk_forward_service.py` | `WalkForwardConfig` gana `hourly_dir` (default `data/klines_1h`); `load_dataset` carga 1h por símbolo y **falla si falta** (evidencia íntegra); `run_walk_forward` propaga hourly al backtest; persiste cada corrida en la nueva tabla. | RF-2, RF-3 |
| `app/services/binance_market_data_client.py` | Ya soporta intervalos (15m/5m usados); se usa `1h` con ≥55 velas. Sin cambio salvo tests. | RF-2 |
| `app/services/bot_loop.py` | En la ventana ORB descarga además klines 1h (55 velas) de los pares ORB y las pasa a `evaluate_orb`; fallo de descarga ⇒ ciclo fallido fail-closed (RNF-6 existente). | RF-1, RF-2, RF-7 |
| `app/models.py` | Tabla `walk_forward_runs`: id, executed_at, verdict, pnl_net_usd, report_path, symbols_json. | RF-4 |
| `app/services/phase_service.py` | Blockers automáticos (D-10): SIMULATION→TESTNET exige último `walk_forward_runs.verdict == "PASA"`; TESTNET→LIVE exige gate de paper (abajo). | RF-4, RF-5 |
| `app/services/phase_service.py` (gate paper) | `compute_paper_gate(db)`: ≥30 decisiones técnicas CERRADAS de la cuenta de paper, expectancy ≥0, máx. drawdown de la curva de equity ≤5% del capital. Sin plazo (D-11). | RF-5 |
| `app/config.py` + `.env` | `configured_capital_usd = 40`, `simulation_initial_balance = 40`. | RF-6 |
| `docs/constitution.md` | Punto 3: inicio de capital 20 → 40 USD (aportado; límites 1 USD/op y 5%/día intactos). | RF-6 |
| Reset cuenta paper | `reset_simulation_account` a 40 USD al desplegar (positions/trades de paper se limpian; el histórico de learning se archiva en el informe antes). | RF-6, D-9 |
| `run_walk_forward.py` | Flag implícita: tras persistir la corrida, imprime verdicto y si desbloquea fase. | RF-4 |
| Descarga datos 1h | `collect_klines.py --interval 1h --data-dir data/klines_1h` para los 5 pares (tarea operativa, usa el recolector existente). | RF-2 |

## Modelo de datos

- `walk_forward_runs` (nueva,append-only): evidencia persistida del gate.
- `signal_decisions.snapshot` (JSON existente): gana `trend_filter: {allowed, close, ema50}` vía `result.metrics` — sin migración.
- Sin cambios en tablas de posiciones/órdenes.

## Estrategia de tests

- `test_trend_filter.py`: EMA con serie conocida (a mano), bordes (<50 velas ⇒ False), solo cerradas, Decimal puro.
- `test_orb_engine.py` (ext): BUY filtrado ⇒ HOLD `trend_filter_reject`; métricas presentes.
- `test_strategy_lab.py` (ext): backtest con hourly que rechaza ⇒ 0 entradas; con hourly que permite ⇒ entradas iguales a sin filtro.
- `test_walk_forward.py` (ext): config sin `hourly_dir` poblado ⇒ error; corrida persiste fila; veredicto correcto.
- `test_phase_gates.py` (nuevo): blockers SIMULATION→TESTNET y TESTNET→LIVE (con y sin evidencia).
- `test_config.py` (ext): capital 40.
- Nada de red: httpx mockeado; fixtures 5m+1h en `fixtures_klines.py`.

## Riesgos conocidos

- El filtro reducirá trades: el walk-forward v2 puede seguir dando NO PASA; se
  iteran parámetros de filtro con los mismos datos (spec lo permite: "se itera").
- El gate de paper (≥30 trades) tomará semanas reales de simulación; es el precio
  del constitución 4 (primero simulado).
