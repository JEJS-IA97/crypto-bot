# Plan 001 — Bot de trading Binance Spot con 20 USD (fase 1)

Referencias: `docs/constitution.md`, `spec.md` (v2), `clarificacion.md`.

> Regla: el plan **no es código**. Define módulos, datos, decisiones y tests. Los parámetros
> finales de la estrategia se fijan en la fase de tareas a partir del backtest (duda abierta #1).

## Alcance de este plan

- **Se construye:** loop autónomo en Binance Spot (8 pares), señales técnicas + externas (copy),
  riesgo acotado, panel web con kill switch, backtest con métricas, fases simulación→testnet→real.
- **Se congela (RF-21), sin tocar un solo fichero:** `arbitrage_service.py`,
  `trade_opportunity_service.py`, `execution_price_service.py`, `bot_engine.py`,
  `bot_runner_service.py`, `exchange_market_service.py`, `okx_demo_client.py`,
  `market_sync_service.py` y sus tests. Se permite **extender** `binance_spot_client.py`
  (es de alcance Binance, no multi-exchange) y reutilizar/`simulation_service.py`.

## Módulos

| # | Módulo (ruta) | Responsabilidad | RF |
|---|---|---|---|
| M1 | `app/services/binance_market_data_client.py` (nuevo) | Klines y exchangeInfo públicos con caché corta y fail-closed | RF-6, RNF-6 |
| M2 | `app/domain/signal_engine.py` (nuevo) | Indicadores + señal determinista `BUY/SELL/HOLD` puro (sin red/BD) | RF-7, RF-23 |
| M3 | `app/services/external_signal_service.py` (nuevo) | Validación de señales externas: side, TTL, precio lejano, pares, duplicados | RF-8, RF-9, RF-23 |
| M4 | `app/domain/risk_math.py` (nuevo) | Cálculos puros: tamaño de orden, stop/tp, tope 1 USD, 25%, 3 posiciones | RF-12, RF-13 |
| M5 | `app/services/risk_guard_service.py` (nuevo) | Estado de riesgo: pérdida diaria, aperturas/día, cooldown, circuit breaker | RF-4, RF-5, RF-22, RF-26 |
| M6 | `app/services/order_lifecycle.py` (nuevo) | Ciclo de vida: fill → stop/tp (OCO) → cierre, slippage, reconciliación | RF-13, RF-24, RF-25, RF-10 |
| M7 | `app/services/binance_executor.py` (nuevo) | Adaptador de `BinanceSpotClient` al protocolo `ExchangeExecutor` + reglas de par | RF-11, RF-14, RF-1, RF-2 |
| M8 | `app/services/bot_loop.py` (nuevo) | Orquestador: evaluar → decidir → riesgo → ejecutar; kill switch; breaker | RF-3, RF-22, RF-5 |
| M9 | `app/services/decision_store.py` (nuevo) | Persistencia de decisiones, snapshot, resultado; métricas del panel | RF-10, RF-17, RF-18 |
| M10 | `app/services/phase_service.py` (nuevo) | Fases simulación/testnet/real + criterios de paso bloqueantes | RF-16, RF-2 |
| M11 | `app/services/strategy_lab_service.py` (existente, extender) | Backtest con comisiones 0.1% + slippage, splits y grid search | RF-15 |
| M12 | `app/api/routes/bot.py`, `signals.py`, `backtest.py` (nuevos) | API REST: estado, kill switch, señales, fase, backtest, auth | RF-3, RF-8, RF-16…RF-20 |
| M13 | `frontend/src/` (adaptar) | Panel: estado, métricas, kill switch, señal externa, historial | RF-17, RF-18, RF-19 |
| M14 | `app/services/simulation_service.py` (existente, extender) | Cuentas/posiciones con stop/tp para paper-trading | RF-4, RF-13, RF-17 |
| F | Zona congelada (RF-21) | Intacta y en verde | RF-21 |

Capas: `app/domain/` es **puro** (sin red, sin BD, sin FastAPI) — testeable aislado. Los servicios
orquestan y persisten; la API es una capa fina. El loop corre como tarea `asyncio` en el lifespan
de FastAPI (una sola instancia, worker único).

## Modelo de datos

Se reutiliza la BD actual (`crypto_bot.db`, SQLite) añadiendo tablas; se activa
`PRAGMA foreign_keys=ON` en `database.py`.

**`signal_decision`** (RF-10, RF-18) — una fila por cada decisión, técnica o externa:
- `id`, `client_order_id` (único ≤36 chars, RF-25)
- `symbol`, `side` (`BUY`|`SELL`), `origin` (`TECHNICAL`|`EXTERNAL`), `source` (fuente externa o NULL)
- `config_json` (indicadores/parámetros usados), `market_snapshot_json` (precio + velas/indicadores + timestamp)
- `status` (`PENDING`|`REJECTED`|`OPENED`|`CLOSED`|`ERROR`), `rejection_reason`
- `quantity`, `price`, `stop_price`, `take_profit_price`
- `filled_at`, `closed_at`, `fees_usd`, `pnl_usd` (se rellenan al cerrar)
- `created_at`, `updated_at`

**`position_v2`** (extiende `simulation_positions`):
- `decision_id` (FK), `stop_price`, `take_profit_price`, `stop_order_id`, `tp_order_id`,
  `status` (`OPEN`|`STOPPED`|`TAKE_PROFIT`|`CLOSED`|`ERROR`), `entry_fee_usd`

**`daily_risk_state`** (RF-4, RF-5):
- `day` (fecha UTC, único), `start_equity_usd`, `realized_pnl_usd`, `opens_count`,
  `blocked` (bool), `block_reason`

**`bot_phase`** (RF-16):
- `phase` (`SIMULATION`|`TESTNET`|`LIVE`), `changed_at`, `evidence_json` (las métricas exigidas),
  `changed_by`

**`bot_runtime`** (RF-3, RF-22) — 1 fila:
- `running` (bool), `breaker_active` (bool), `consecutive_failures`, `breaker_reason`, `updated_at`

**Sin cambios:** `simulation_accounts`, `simulation_balances`, `simulation_trades`;
**intocables:** `simulation_arbitrages`, `simulation_bot_cycles` (zona congelada).

`external_signal_log` **no** es una tabla aparte: las señales externas rechazadas se guardan
como `signal_decision.status = REJECTED` con su motivo (RF-18).

## Algoritmo / flujo principal (loop, M8)

1. Si `bot_runtime.running == false` o `breaker_active` → dormir (kill switch / breaker).
2. Cargar `daily_risk_state` de hoy; si `blocked` → no abrir nuevas (los stops siguen en M6).
3. Descargar klines (15m) + exchangeInfo de los 8 pares (M1). Cualquier fallo → ciclo fallido
   (fail-closed, RNF-6) y sumar al contador del breaker (RF-22 a los 5).
4. Para cada par con posición abierta → M6 comprueba fills de stop/tp y actualiza la decisión (RF-10).
5. Para cada par **sin** posición → M2 genera la señal técnica.
6. Procesar señales externas en cola (M3): validadas por TTL/side/precio/duplicados.
7. Conflicto técnico vs externa sobre el mismo par → gana la externa (RF-23).
8. Si hay señal `BUY` → M4 calcula tamaño (mín. notional, tope 25%, ≤3 posiciones) → M5 valida
   pérdida diaria, aperturas/día y cooldown → si aprueba, M7 envía la orden con `clientOrderId`
   idempotente (RF-25) → M6 coloca stop/tp y persiste todo (RF-10).
9. Señal `SELL` sobre posición propia → M6 cierra y registra PnL con comisiones.
10. Actualizar métricas (M9) y dormir hasta el siguiente intervalo (config, defecto 60 s).

## Decisiones justificadas

### Decisión 1: Empezar en paper-trading local, no en testnet
- **Elegido:** fase 1 = simulación en la propia BD; testnet solo tras RF-16.
- **Alternativa descartada:** ir directo a Binance testnet para "probar de verdad".
- **Motivo:** constitución #4 (doble confirmación) y D-5; además el testnet no valida métricas de
  1 mes. El simulador existente ya funciona y está testeado.

### Decisión 2: Stop/tp como órdenes en el exchange, no supervisadas por el loop
- **Elegido:** al llenar la compra, colocar **OCO de salida** (limit de take-profit + stop-loss de
  mercado) en Binance; en simulación se modelan igual. El loop solo reconcilia (M6).
- **Alternativa descartada:** el loop vigila el precio y vende cuando toca (stops "de software").
- **Motivo:** si el proceso se cae, los stops del exchange siguen vivos → protección real
  (constitución #3, RF-13). Es la única forma de que el kill switch no deje posiciones desprotegidas.

### Decisión 3: Temporalidad 15m por defecto (no 1m)
- **Elegido:** velas de 15m, configurable.
- **Alternativa descartada:** 1m para "más señales".
- **Motivo:** con 10 aperturas/día máximo (RF-5), comisiones 0.1%×2 y slippage, 1m genera ruido y
  señales que no caben en los límites; 15m da ~96 velas/día, suficiente para RSI/EMA.

### Decisión 4: Estrategia por reglas + grid search, no modelo ML
- **Elegido:** conjunto candidato de reglas sobre **EMA(20/50), RSI(14) y volumen** (compra:
  cruce alcista + RSI en zona de valor; venta: cruce bajista, RSI sobrecomprado o stop/tp),
  parámetros elegidos por grid search en backtest y registrados aquí como "Parámetros finales".
- **Alternativa descartada:** red neuronal/predicción de precio.
- **Motivo:** constitución #9 (sin métrica no entra); con 3.903 snapshots existentes y klines
  históricos descargables de Binance (hasta años, sin esperar 30 días) hay datos para backtest,
  no para entrenar un modelo fiable. Un ML posterior exigirá spec propia (fuera de alcance).

### Decisión 5: Backtest sobre klines históricos de Binance, no sobre los snapshots actuales
- **Elegido:** nuevo recolector de klines (`/api/v3/klines`, histórico en bloques de 1000 velas)
  → JSONL en `backend/data/klines/*.jsonl` → M11.
- **Alternativa descartada:** reutilizar `data/market_snapshots.jsonl` (book ticker de 4 exchanges).
- **Motivo:** los snapshots actuales **no tienen velas** (no hay OHLCV) y son solo 6 horas;
  además son de la zona multi-exchange congelada.

### Decisión 6: Token simple por entorno, no sistema de usuarios
- **Elegido:** `API_TOKEN` en `.env`; obligatorio en fases `testnet`/`real`, opcional en
  simulación (RF-20).
- **Alternativa descartada:** login con usuarios, roles y sesiones.
- **Motivo:** fuera de alcance (un solo propietario, panel local); minimiza dependencias
  (constitución #12) sin dejar la API de control abierta cuando hay dinero real.

### Decisión 7: Loop en el proceso de FastAPI (worker único), no worker externo
- **Elegido:** tarea `asyncio` en el lifespan (patrón ya usado por `main.py`), con
  `execution_lock` y `bot_runtime` persistido.
- **Alternativa descartada:** Celery/Redis/programador externo.
- **Motivo:** 20 USD y una máquina; Redis/Celery añaden infraestructura y modos de fallo
  nuevos (constitución #12). Se documenta el límite: **no** lanzar uvicorn con `--workers >1`.

### Decisión 8: Adaptar el panel existente, no reescribir
- **Elegido:** reutilizar `frontend/src` (React+Vite ya funcionando), sustituir el MarketPanel de
  precios manuales por panel de bot (estado, métricas, kill switch, señal externa, historial).
- **Alternativa descartada:** nueva UI o CLI sola.
- **Motivo:** D-6 (panel web); ya hay axios y estructura; reescribir consume tareas sin aportar.

### Decisión 9: Frontend crítico testeado con Vitest
- **Elegido:** `vitest` + `@testing-library/react` solo para los 3 componentes críticos
  (kill switch, formulario de señal externa, tarjetas de métricas).
- **Alternativa descartada:** sin tests de frontend (o tests e2e con Playwright).
- **Motivo:** constitución #8 (RF sin test = no implementado) — RF-19 es UI; Playwright es
  infraestructura pesada para este alcance.

## Contrato público (API / CLI / interfaz)

Todas las rutas bajo `/api`. JSON. Pydantic v2 con validación estricta.

| Método y ruta | Entrada | Salida | RF |
|---|---|---|---|
| `GET /api/bot/status` | — | fase, running, breaker, métricas resumidas, último error | RF-17, RF-18 |
| `POST /api/bot/start` | — | estado nuevo (requiere token si fase ≠ simulación) | RF-3, RF-19, RF-20 |
| `POST /api/bot/stop` | — | estado nuevo (`running=false` en ≤5 s) | RF-3, RF-19 |
| `POST /api/signals/external` | `{symbol, side, price_limit?, quantity?, quantity_quote?, source, ttl_seconds?}` | `accepted`/`rejected` + motivo | RF-8, RF-9, RF-19 |
| `POST /api/webhooks/signal` | igual + `?token=` | igual (para fuentes con webhook) | RF-8, RF-20 |
| `GET /api/signals/decisions` | filtros (fecha, símbolo, estado) | lista de decisiones con snapshot y resultado, incl. rechazadas | RF-10, RF-18 |
| `GET /api/bot/metrics` | — | saldo, posiciones, PnL, drawdown, aperturas/pérdida del día | RF-17 |
| `GET /api/bot/phase` / `POST /api/bot/phase` | `{phase, evidence}` | fase actual o motivo de rechazo (bloqueo si no cumple RF-16) | RF-16, RF-20 |
| `POST /api/backtest` | `{params, symbol_list, date_range}` | rentabilidad, drawdown, operaciones, win rate | RF-15 |
| `GET /health` | — | ok (ya existe) | — |

CLI existentes que se conservan: `collect_market_snapshots.py` (zona multi-exchange, congelado),
`train_strategy.py` (se amplía para klines, M11), `check_binance_testnet.py`, `check_okx_demo.py`.

## Estrategia de tests

- **Unitarios (sin red, `app/domain/` y servicios con mocks):** determinismo de la señal sobre
  fixtures de klines; matemáticas de tamaño/stop/tp (Decimal); bloqueo por pérdida diaria;
  aperturas/cooldown; TTL y rechazos de señal externa; conflicto de señales; circuit breaker;
  idempotencia de `clientOrderId`; comisiones y slippage en backtest; fases bloqueadas.
- **Integración (httpx mockeado, SQLite en memoria):** ciclo completo del loop (evaluar → decidir
  → orden simulada → stop/tp → cierre con PnL); kill switch durante un ciclo en vuelo;
  reconciliación tras "corte de proceso"; API con `TestClient` (todas las rutas, incluida la auth).
- **Frontend (vitest + testing-library):** kill switch, formulario de señal externa con validación,
  métricas.
- **Regresión de zona congelada (RF-21):** la suite multi-exchange existente debe seguir en verde
  sin modificaciones — si un fichero congelado cambia, el test falla.
- **Manual/no automatizado:** paper-trading de 30 días (RF-16) y pruebas contra testnet real.

## Mapeo RF → módulo → test

| RF | Módulo | Test |
|----|--------|------|
| RF-1 | M7 | `tests/test_execution_mode.py::test_no_live_without_flag` |
| RF-2 | M10, M7 | `tests/test_phase_service.py::test_refuses_live_without_capital` |
| RF-3 | M8, M12 | `tests/test_kill_switch.py::test_stop_during_cycle` |
| RF-4 | M5 | `tests/test_daily_risk.py::test_blocks_after_5pct_loss` |
| RF-5 | M5 | `tests/test_daily_risk.py::test_open_limit_and_cooldown` |
| RF-6 | M1 | `tests/test_binance_market_data.py::test_fail_closed_on_error` |
| RF-7 | M2 | `tests/test_signal_engine.py::test_deterministic_signal` |
| RF-8 | M3, M12 | `tests/test_external_signals.py::test_ttl_and_price_distance` |
| RF-9 | M3 | `tests/test_external_signals.py::test_duplicate_and_unknown_symbol` |
| RF-10 | M9, M6 | `tests/test_decision_audit.py::test_snapshot_and_result` |
| RF-11 | M7 | `tests/test_order_rules.py::test_min_notional_from_exchange_info` |
| RF-12 | M4 | `tests/test_position_sizing.py::test_min_notional_cap_and_rounding` |
| RF-13 | M4, M6 | `tests/test_order_lifecycle.py::test_stop_loss_capped_1usd` y `::test_error_without_stop` |
| RF-14 | M7 | `tests/test_credentials_guard.py::test_fails_safe_without_keys` |
| RF-15 | M11 | `tests/test_strategy_lab.py::test_fees_and_slippage` (ampliar) |
| RF-16 | M10 | `tests/test_phase_service.py::test_requires_30d_15ops_drawdown` |
| RF-17 | M9, M12 | `tests/test_metrics_api.py::test_metrics_payload` |
| RF-18 | M12, M13 | `tests/test_bot_api.py::test_status_and_history` + vitest de panel |
| RF-19 | M12, M13 | `tests/test_bot_api.py::test_start_stop_and_signal` + vitest del formulario |
| RF-20 | M12 | `tests/test_bot_api.py::test_token_required_in_live` |
| RF-21 | Zona congelada | `tests/test_frozen_zone.py::test_frozen_files_unchanged_and_green` |
| RF-22 | M5, M8 | `tests/test_circuit_breaker.py::test_stops_after_5_failures` |
| RF-23 | M2, M3, M8 | `tests/test_signal_conflict.py::test_external_wins` |
| RF-24 | M6 | `tests/test_order_lifecycle.py::test_slippage_reported` |
| RF-25 | M7 | `tests/test_order_rules.py::test_client_order_id_unique` |
| RF-26 | M5, M8 | `tests/test_daily_risk.py::test_reentry_after_exit` |
| RNF-1 | todos | aserciones `Decimal` en `test_position_sizing.py` + revisión estática |
| RNF-2 | suite | ejecución sin credenciales (CI local) |
| RNF-3 | M8, M12 | `tests/test_bot_api.py::test_api_responsive_during_loop` |
| RNF-4 | M7, M12 | `tests/test_credentials_guard.py::test_no_keys_in_logs` |
| RNF-5 | M7 | ver RF-25 |
| RNF-6 | M1, M8 | `tests/test_binance_market_data.py::test_fail_closed_on_error` + `::test_stale_cache_is_never_served` |
| RNF-7 | revisión | convención (AGENTS.md) |

## Riesgos del plan
1. **15 operaciones en 30 días:** con 8 pares y señales técnicas puede no alcanzarse el mínimo de
   RF-16 → si ocurre, se amplía el periodo (decisión del propietario, no del código).
2. **Comisiones/stop mal calibrados** → el grid search sobre klines históricos es la primera tarea
   de validación de la estrategia antes de gastar tareas en la UI.
3. **Zona congelada:** cualquier "mejora" tentativa a los ficheros congelados rompe RF-21; el test
   de congelación lo detecta.
