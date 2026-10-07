# Tareas 001 — Bot de trading Binance Spot con 20 USD (fase 1)

Cada tarea dura **<30 min**, tiene sus RF y un "Hecho cuando:" verificable.
Ordenadas por dependencia. Marca `[x]` solo tras tests en verde.

Referencias: `plan.md` (módulos M1-M14), `spec.md` v3 (RF-1…RF-27).

## Bloque 0 — Base

- [x] **T1** — Configuración y entorno
  - RF: RF-1, RF-2, RF-14, RF-20
  - Hecho cuando: `app/config.py` expone `ALLOW_LIVE_TRADING` (defecto `false`), `CONFIGURED_CAPITAL_USD` (20), `API_TOKEN` (vacío), `SIMULATION_BOT_*` (intervalo, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`, `MAX_SIGNAL_PRICE_DISTANCE_PCT`, `SIGNAL_TTL_SECONDS`), y `.env.example` los lista; `database.py` activa `PRAGMA foreign_keys=ON`; `requirements.txt` con versiones fijadas.
  - Tests: `tests/test_config.py::test_live_trading_disabled_by_default`, `tests/test_config.py::test_foreign_keys_on`

- [x] **T2** — Modelos de datos nuevos
  - RF: RF-4, RF-5, RF-10, RF-16, RF-22
  - Hecho cuando: `models.py` define `SignalDecision`, `PositionV2`, `DailyRiskState`, `BotPhase`, `BotRuntime` con los campos del plan; las tablas se crean al arrancar sin romper las existentes; `simulation_arbitrages` y `simulation_bot_cycles` siguen intactas.
  - Tests: `tests/test_models_new_tables.py::test_tables_created_and_frozen_untouched`

## Bloque 1 — Dominio puro

- [x] **T3** — Motor de señales determinista
  - RF: RF-7
  - Hecho cuando: `app/domain/signal_engine.py` calcula EMA/RSI/volumen en `Decimal` y devuelve `BUY`/`SELL`/`HOLD`; mismas velas + misma config → misma señal (test repetido); sin importar red ni BD.
  - Tests: `tests/test_signal_engine.py::test_deterministic_signal`, `::test_buy_and_sell_cases`

- [x] **T4** — Matemáticas de riesgo
  - RF: RF-12, RF-13
  - Hecho cuando: `app/domain/risk_math.py` calcula tamaño de orden `max(mínimo notional, hasta 25% del aporte)` redondeado al `stepSize`, distancia de stop/tp en %, verifica que la pérdida con stop ≤1 USD y devuelve `descartar` cuando no se cumple; todo en `Decimal`.
  - Tests: `tests/test_position_sizing.py::test_min_notional_cap_and_rounding`, `::test_loss_capped_at_1usd`, `::test_decimal_types`

## Bloque 2 — Datos de mercado

- [x] **T5** — Cliente de klines/exchangeInfo
  - RF: RF-6, RNF-6
  - Hecho cuando: `app/services/binance_market_data_client.py` descarga `/api/v3/klines` (temporalidad configurable, defecto 15m) y `/api/v3/exchangeInfo` con caché corta; si Binance falla o los datos están caducados → `fail-closed` (señal de "sin datos", ninguna operación); sin credenciales.
  - Tests: `tests/test_binance_market_data.py::test_klines_ok`, `::test_fail_closed_on_error`

## Bloque 3 — Riesgo

- [x] **T6** — Guardián de riesgo (pérdida diaria, límites, breaker)
  - RF: RF-4, RF-5, RF-22, RF-26
  - Hecho cuando: `app/services/risk_guard_service.py` persiste `daily_risk_state` (inicio de día, PnL, aperturas, bloqueo), bloquea aperturas al ≥5% de pérdida del día UTC dejando stops vigentes, aplica 10 aperturas/día + cooldown 300 s por par, cuenta 5 fallos seguidos → breaker, y permite reabrir tras un cierre si no hay bloqueo.
  - Tests: `tests/test_daily_risk.py::test_blocks_after_5pct_loss`, `::test_open_limit_and_cooldown`, `::test_reentry_after_exit`, `tests/test_circuit_breaker.py::test_stops_after_5_failures`

## Bloque 4 — Señales externas (copy)

- [x] **T7** — Validador de señales externas
  - RF: RF-8, RF-9, RF-23
  - Hecho cuando: `app/services/external_signal_service.py` valida `{symbol, side, price_limit?, quantity?, quantity_quote?, source, ttl_seconds}`: enum `side`, TTL (defecto 300 s), par dentro de los 8, precio no alejado >`MAX_SIGNAL_PRICE_DISTANCE_PCT`, sin duplicado en cooldown; calcula la cantidad si falta (vía T4); conflicto con señal técnica sobre el mismo par → gana la externa y la técnica queda `no ejecutada`.
  - Tests: `tests/test_external_signals.py::test_ttl_and_price_distance`, `::test_duplicate_and_unknown_symbol`, `::test_external_wins_on_conflict`

## Bloque 5 — Ejecución

- [x] **T8** — Adaptador Binance → protocolo de ejecución
  - RF: RF-11, RF-14, RF-1, RF-2, RF-25
  - Hecho cuando: `app/services/binance_executor.py` implementa `ExchangeExecutor` sobre `BinanceSpotClient`, consulta `exchangeInfo` (`LOT_SIZE`, `PRICE_FILTER`, `MIN_NOTIONAL`/`NOTIONAL`) y rechaza órdenes inválidas con motivo; genera `clientOrderId` único por decisión (sin duplicados en reintento); sin claves → falla seguro (sin órdenes); `ALLOW_LIVE_TRADING` ≠ `true` → no envía a producción.
  - Tests: `tests/test_order_rules.py::test_min_notional_from_exchange_info`, `::test_client_order_id_unique`, `tests/test_credentials_guard.py::test_fails_safe_without_keys`, `tests/test_execution_mode.py::test_no_live_without_flag`

- [x] **T9** — Ciclo de vida de órdenes en simulación (stop/tp, cierre, slippage)
  - RF: RF-13, RF-24, RF-10
  - Hecho cuando: `app/services/order_lifecycle.py` sobre `SimulationExecutor`: al llenar una compra coloca stop de mercado y take-profit (una posición por par, se cancelan mutuamente), si no logra colocar el stop → posición `ERROR` y bloqueo de aperturas; al cerrar calcula PnL con comisión 0.1% por lado; fill con slippage >0.5% → incidente registrado.
  - Tests: `tests/test_order_lifecycle.py::test_stop_loss_and_take_profit_mutual_cancel`, `::test_error_without_stop`, `::test_slippage_reported`, `::test_fees_in_pnl`

- [x] **T10** — Almacén de decisiones y métricas
  - RF: RF-10, RF-17
  - Hecho cuando: `app/services/decision_store.py` persiste cada decisión con `client_order_id`, snapshot (precio + velas/indicadores + config) y, al cerrar, `filled_at/closed_at/fees/pnl`; expone métricas (saldo, posiciones, PnL realizado/no, drawdown, aperturas y pérdida del día) con latencia ≤5 s.
  - Tests: `tests/test_decision_audit.py::test_snapshot_and_result`, `tests/test_metrics_api.py::test_metrics_payload`

## Bloque 6 — Loop autónomo

- [x] **T11** — Loop con kill switch, breaker y flujo completo
  - RF: RF-3, RF-5, RF-22, RF-23, RF-1, RNF-3, RNF-6
  - Hecho cuando: `app/services/bot_loop.py` ejecuta el flujo del plan (evaluar → señal técnica/externa → riesgo → orden → persistir) en modo simulación; `POST /api/bot/stop` detiene el loop en ≤5 s sin reiniciar y no salen órdenes nuevas mientras tanto; 5 fallos seguidos → breaker con reinicio manual; la API responde mientras el loop evalúa; sin datos frescos → no opera.
  - Tests: `tests/test_kill_switch.py::test_stop_during_cycle`, `tests/test_circuit_breaker.py::test_breaker_blocks_orders`, `tests/test_bot_api.py::test_api_responsive_during_loop`

## Bloque 7 — Fases

- [x] **T12** — Servicio de fases con criterios de paso
  - RF: RF-16, RF-2
  - Hecho cuando: `app/services/phase_service.py` persiste la fase en BD y solo permite `SIMULATION→TESTNET` si hay ≥30 días de paper-trading con PnL neto >0 tras comisiones, ≥15 operaciones, drawdown ≤10% y backtest positivo en validación y test; `TESTNET→LIVE` exige además testnet rentable; sin cumplir → rechaza con el detalle de lo que falta; `ALLOW_LIVE_TRADING=true` con fase ≠ `LIVE` o aporte superado → rechazo visible.
  - Tests: `tests/test_phase_service.py::test_requires_30d_15ops_drawdown`, `::test_refuses_live_without_capital`

## Bloque 8 — API

- [x] **T13** — Rutas REST del bot y auth
  - RF: RF-3, RF-8, RF-16, RF-18, RF-19, RF-20, RNF-3
  - Hecho cuando: existen `GET /api/bot/status`, `POST /api/bot/start|stop`, `POST /api/signals/external`, `POST /api/webhooks/signal`, `GET /api/signals/decisions` (incluye rechazadas con motivo), `GET /api/bot/metrics`, `GET|POST /api/bot/phase`; token obligatorio en fases `TESTNET`/`LIVE`, opcional en `SIMULATION`; entrada validada con Pydantic; respuestas en español para mensajes de estado.
  - Tests: `tests/test_bot_api.py::test_status_and_history`, `::test_start_stop_and_signal`, `::test_token_required_in_live`

## Bloque 9 — Backtest

- [x] **T14** — Recolector de klines históricos
  - RF: RF-15 (soporte de datos)
  - Hecho cuando: `backend/collect_klines.py` descarga histórico de `/api/v3/klines` por bloques de 1000 velas para los 8 pares, escribe `data/klines/*.jsonl` y es reanudable (continúa donde iba); corre sin credenciales.
  - Tests: `tests/test_collect_klines.py::test_chunk_download_and_resume` (httpx mockeado)

- [x] **T15** — Backtest con comisiones y grid search
  - RF: RF-15
  - Hecho cuando: `strategy_lab_service.py` consume klines, modela comisión 0.1% por lado + slippage configurable, mantiene splits sin look-ahead, reporta rentabilidad neta/drawdown/operaciones/win rate y compara configuraciones (grid); `train_strategy.py` corre el grid sobre klines y **escribe los "Parámetros finales" en `plan.md`** (§ pendiente de duda abierta #1).
  - Tests: `tests/test_strategy_lab.py::test_fees_and_slippage`, `::test_grid_ranking`

## Bloque 10 — Panel web

- [x] **T16** — Panel de estado y métricas
  - RF: RF-17, RF-18
  - Hecho cuando: el panel muestra fase, estado (activo/detenido/bloqueado + motivo), métricas (saldo, posiciones, PnL, drawdown, aperturas y pérdida del día), historial de decisiones con snapshot y resultado, y señales rechazadas con motivo; se elimina el MarketPanel de precios escritos a mano; auto-refresh ≤5 s.
  - Tests: `frontend`: `src/components/__tests__/MetricsPanel.test.jsx` (vitest) + `tests/test_bot_api.py::test_status_and_history`

- [x] **T17** — Kill switch y señal externa en el panel
  - RF: RF-3, RF-8, RF-19
  - Hecho cuando: botones Arrancar/Detener conectados a la API (el Detener refleja `running=false` en ≤5 s) y formulario de señal externa (par, lado, precio, cantidad, fuente) que muestra `aceptada`/`rechazada + motivo`; ambos con tests de componente.
  - Tests: `frontend`: `src/components/__tests__/KillSwitch.test.jsx`, `src/components/__tests__/ExternalSignalForm.test.jsx`

## Bloque 11 — Congelación y validación

- [x] **T18** — Test de zona congelada
  - RF: RF-21
  - Hecho cuando: `tests/test_frozen_zone.py` verifica por hash que los 8 ficheros multi-exchange congelados no han cambiado desde el inicio de la fase 1 y que su suite existente sigue en verde.
  - Tests: `tests/test_frozen_zone.py::test_frozen_files_unchanged_and_green`

- [x] **T19** — Validación RF por RF y limpieza
  - RF: todos
  - Hecho cuando: recorrido de `spec.md` RF por RF confirmando el test que lo cubre (Fase 7 SDD), suite completa en verde, sin código sin RF (código muerto de módulos no congelados eliminado), `python -m compileall app tests` sin errores y `requirements`/README actualizados.
  - Tests: suite completa + `compileall`

- [x] **T20** — Conexión a Binance testnet (manual, fuera de la suite diaria)
  - RF: RF-14, RF-16 (preparación)
  - Hecho cuando: con credenciales en `.env`, `check_binance_testnet.py` conecta y lee cuenta/exchangeInfo; documentado en README con el paso a fase `TESTNET` (solo se usará cuando RF-16 lo permita).
  - Tests: manual (marcado como no parte de la suite, RNF-2)

## Bloque 12 — Estrategia ORB (spec v3)

- [x] **T21** — Dominio ORB determinista
  - RF: RF-7 (v3)
  - Hecho cuando: `app/domain/orb_engine.py` (módulo puro, sin red/BD) devuelve `BUY`/`HOLD` según el rompimiento del rango 9:00–9:30 AM `America/New_York` sobre velas 5m: `BUY` si el cierre de la vela en curso supera el máximo del rango dentro de la ventana 9:30–10:00 NY; `HOLD` con motivo (`breakdown_no_short`, `no_breakout`, `range_incomplete`, `breakout_candle_missing`, `before_range_close`, `breakout_window_closed`) en el resto; determinista (mismas velas + mismo instante → misma salida), horario de verano/invierno correcto, todo `Decimal`; `signal_engine.py` (EMA/RSI) intacto como candidata de backtest; `tzdata` declarado en `requirements.txt` (constitución #12).
  - Tests: `tests/test_orb_engine.py` (nuevo)

- [x] **T22** — Integración ORB en el loop
  - RF: RF-6, RF-7 (v3), RF-27, RF-23, D-11, D-12
  - Hecho cuando: `bot_loop.py` descarga klines 5m solo en la ventana ORB para los 4 pares (D-12) y opera el flujo con `evaluate_orb` (sin `SELL` técnico: cierres por RF-13/RF-8); una sola decisión técnica por par por día NY (RF-27, consultada en `decision_store`); snapshot de la decisión incluye el rango ORB; `TAKE_PROFIT_PCT` por defecto = `STOP_LOSS_PCT` (RR 1:1, D-11); pares no ORB solo con señales externas.
  - Tests: `tests/test_orb_loop.py` (nuevo) + ajuste de `tests/test_signal_conflict.py`, `tests/test_kill_switch.py`, `tests/test_circuit_breaker.py`, `tests/test_config.py`

- [x] **T23** — Backtest ORB con salidas TP/SL
  - RF: RF-15
  - Hecho cuando: `strategy_lab_service.py` añade backtest ORB sobre klines 5m: entra en el rompimiento de 9:30 AM NY, sale por take-profit/stop (RR 1:1) o al cerrar la ventana del día, con comisión 0.1% por lado, slippage configurable y splits train/valid/test sin look-ahead; `train_strategy.py` puede comparar ORB frente a la candidata EMA/RSI (grid).
  - Tests: `tests/test_strategy_lab.py` (ampliar: clase `OrbKlineBacktestTest`, 13 tests) + `tests/test_orb_engine.py` (helpers `ny_datetime`/`session_bounds`)

- [x] **T24** — Validación RF por RF de la spec v3 y limpieza
  - RF: todos
  - Hecho cuando: recorrido RF por RF de `spec.md` v3 (incluidos RF-27 y los casos límite ORB), suite completa en verde, sin código sin RF, `compileall` sin errores, README/`.env.example` actualizados con la estrategia ORB.
  - Tests: suite completa + `compileall`

---

## Reglas para marcar una tarea como hecha

1. Tests escritos **antes** del código de producción.
2. Suite completa en verde.
3. Salida de tests adjunta en el mensaje al usuario.
4. RF asociados verificados.
5. Solo entonces: `[x]` y parar.
