# Tareas — spec 012: estrategia ORB v2

Orden por dependencia. Cada tarea <30 min, tests primero.

- [x] **T1** `app/domain/trend_filter.py` + `tests/test_trend_filter.py` — RF-1, RF-2 parcial, RF-8.
  Hecho cuando: `compute_ema` reproduce una EMA known-case en Decimal y `trend_allows` devuelve False con <50 velas cerradas, False si close < EMA, True si close ≥ EMA; suite del módulo en verde.

- [x] **T2** `orb_engine.evaluate_orb` acepta `hourly_candles` y filtra BUY → HOLD `trend_filter_reject` con métricas — RF-1.
  Hecho cuando: test existente de ORB sigue verde y los nuevos de filtro (reject/allow) pasan; `result.metrics` incluye `trend_filter_close` y `trend_filter_ema50`.

- [x] **T3** `strategy_lab_service`: `OrbBacktestConfig.hourly_candles` + compuerta en `backtest_orb` — RF-3, RF-7.
  Hecho cuando: fixture 5m+1h con filtro en falso produce 0 entradas y con filtro en verdadero produce las mismas entradas que sin hourly; tests en verde.

- [x] **T4** `walk_forward_service`: `hourly_dir`, carga 1h con fallo si falta, propaga al backtest — RF-2, RF-3.
  Hecho cuando: config sin archivos 1h ⇒ `FileNotFoundError`/error claro; con fixtures 5m+1h el pipeline corre y aplica filtro; tests en verde.

- [x] **T5** `models.py` tabla `walk_forward_runs` + persistencia desde `run_walk_forward` + `walk_forward_cli` la imprime — RF-4 parcial.
  Hecho cuando: una corrida (fixtures) deja fila con verdicto y pnl; test en verde.

- [x] **T6** `phase_service`: blocker automático SIMULATION→TESTNET exige último run PASA — RF-4.
  Hecho cuando: test prueba 409 sin run PASA y success con run PASA persistido.

- [x] **T7** `phase_service.compute_paper_gate` + blocker TESTNET→LIVE — RF-5.
  Hecho cuando: con <30 trades cerrados ⇒ blocked; con ≥30, expectancy≥0 y DD≤5% ⇒ allowed; con expectancy<0 ⇒ blocked; tests en verde.

- [x] **T8** Capital 40: `config.py`, `.env`, `.env.example`, `docs/constitution.md` punto 3, reset cuenta paper vía `reset_simulation_account` — RF-6.
  Hecho cuando: `Settings(_env_file=None).configured_capital_usd == 40` y `simulation_initial_balance == 40`; test actualizado en verde; cuenta reiniciada a 40 USD.

- [ ] **T9** `bot_loop` descarga klines 1h (55 velas) en ventana ORB y las pasa a `evaluate_orb` — RF-1, RF-2, RF-7.
  Hecho cuando: test con cliente mockeado verifica que pide intervalo `1h` y que el HOLD `trend_filter_reject` persiste en la decisión; suite en verde.

- [ ] **T10** Operativa: descargar 1h reales de los 5 pares a `data/klines_1h` y ejecutar walk-forward v2 — RF-2, RF-3, finalización 1.
  Hecho cuando: informe `reports/walk-forward-*.md` con veredicto mostrado al propietario y fila persistida.

- [ ] **T11** Validación RF por RF + docs (README: sección v2) — cierre.
  Hecho cuando: checklist RF→test→resultado completo y suite global en verde.
