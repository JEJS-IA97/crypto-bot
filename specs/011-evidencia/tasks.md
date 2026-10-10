# Tareas — Spec 011 (Evidencia: walk-forward ORB)

Orden por dependencia. Tests primero (rojo→verde). Al final de cada tarea: suite completa backend + ruff + compileall, reporte de RF cubiertos y **PÁRATE** hasta aprobación.

- [x] **T1 · Fixtures + folds rojos** — `tests/fixtures_klines.py` (generador JSONL 5m con sesión NY poblada) y `tests/test_walk_forward.py` rojos para `validate_candles` y `build_folds` (`app/services/walk_forward_service.py` aún no implementado). RF-1, RF-2 (construcción), RF-9 (determinismo parcial).
  *Hecho cuando:* la suite falla por `ImportError`/`AttributeError` en los tests nuevos y los existentes siguen en verde. ✅ (2026-10-09: 505 tests, 1 error esperado `ModuleNotFoundError: walk_forward_service`; 504 verdes; ruff+compileall OK)

- [x] **T2 · Folds + grid + selección verdes** — Implementar `validate_candles`, `build_folds`, `iter_grid` (filtro ≤1 USD, const. #3) y `select_params` (validación interna 15 %, const. #9). RF-2 completo.
  *Hecho cuando:* `test_walk_forward.py` en verde, incl. el test de no-look-ahead (pico solo en test no cambia el ganador del train) y la construcción exacta train `[t,t+180d)`/test `[t+180d,t+210d)`/paso 30 d (parametrizado con ventanas pequeñas). ✅ (2026-10-09: 24/24 del módulo; suite 528/528 OK; ruff+compileall OK)

- [x] **T3 · Métricas rojo→verde** — `tests/test_wf_metrics.py` (costes en fees; 5 métricas contra valores a mano; profit factor `n/a`; Sharpe 0) y luego `daily_sharpe`, `max_drawdown`, cálculo de `FoldMetrics`/agregado en el servicio. RF-3, RF-4.
  *Hecho cuando:* `test_wf_metrics.py` en verde y la agregación (suma aritmética de PNl de test, D-7) está verificada con un dataset de 2 folds. ✅ (2026-10-09: 12/12; suite 540/540 OK; ruff+compileall OK. Nota: se añadió `trade_list` aditivo a `KlineBacktestResult` (backtest_orb) para exponer trades sin tocar la lógica de señales)

- [x] **T4 · Gate + reporte + CLI rojo→verde** — `tests/test_walk_forward_cli.py` y después `run_walk_forward.py`, `render_report`, `run_walk_forward` orquestador con gate `PASA ⇔ agregado > 0`, exit codes, `.gitignore` de `backend/reports/`. RF-5, RF-6, RF-7.
  *Hecho cuando:* fixtures positivas ⇒ PASA y exit 0; fixtures negativas ⇒ NO PASA y exit 0; dataset ausente ⇒ exit 1; el Markdown generado contiene las secciones obligatorias (folds, agregado, buy & hold, veredicto). ✅ (2026-10-10: 8/8; suite 548/548 OK; ruff+compileall OK. El backtest es por símbolo (el motor agrupa por día NY sin símbolo) y los trades se combinan por fold)

- [x] **T5 · Aislamiento + cierre** — `tests/test_walk_forward_isolation.py` (sin red, sin DB, sin `bot_loop`), docs (sección "Evidencia walk-forward (spec 011)" en `backend/README*.md` si aplica), estado de spec a `implementada`, validación final RF por RF. RF-8.
  *Hecho cuando:* suite completa + ruff + compileall en verde, RF-8 verificado y `spec.md`/`tasks.md` actualizados. ✅ (2026-10-10: 2/2 aislamiento; suite 550/550 OK; ruff `.` + compileall OK; README backend actualizado; spec en estado `implementada`)
