# Tasks — Spec 005

Ver `spec.md` y `plan.md`. Metodología: TDD (rojo → verde), suite completa en verde,
marcar checkbox y reportar antes de pasar a la siguiente tarea.

- [x] **T1 — Tests rojos de observabilidad.** `tests/test_observability.py`
  (StructuredLogTests, CorrelationIdTests, EventPersistenceTests, RedactionTests,
  SourceHealthTests, RetentionTests) y `tests/test_observability_api.py`
  (EventsEndpointTests, ObservabilityEndpointTests). Importan módulos que aún no
  existen (rojo por ImportError) o fallan por campos ausentes.

- [x] **T2 — Modelos y config.** `SystemEvent` y `SourceHealth` en `models.py`;
  settings `event_retention_days`, `log_level`, `strategy_version`;
  `test_models_new_tables.py` ampliado (NEW_TABLES + `source_health`);
  tablas congeladas intactas.

- [x] **T3 — `structured_log`.** `JsonFormatter` con campos obligatorios (RF-1),
  `configure_logging()`, `redact()` de campos prohibidos (RF-4) y `emit()`
  fail-open (D-3, RF-1/RNF-2).

- [x] **T4 — `observability_service`.** `record_event` (payload ≤ 4 KB),
  `mark_source`/`sources_state` (STALE/DISABLED), `purge_old_events` (RF-8),
  `aggregates_24h` (RF-7).

- [x] **T5 — Instrumentación de loop y órdenes.** `correlation_id` por ciclo en
  `run_once` (RF-2), `cycle.completed` con latencia (RF-1), inyección en
  `snapshot` de decisiones, `decision.emitted/blocked`, `order.*` en
  `order_lifecycle`/`binance_executor`, marcaje de fuentes en los `except`
  existentes. **La suite de 001 debe seguir verde sin editar aserciones (RF-9).**

- [x] **T6 — API y arranque.** Router `observability.py` con
  `GET /api/bot/events` (clamps 1…200, filtros), `GET /api/bot/sources`,
  `GET /api/bot/observability`; registro en `main.py` + `configure_logging()` y
  purga inicial en el lifespan (RF-5, RF-6, RF-7).

- [x] **T7 — Documentación y validación final.** `.env.example` y
  `backend/README.md` (vars nuevas, sección "Observabilidad", endpoints);
  `ruff check .` limpio; `python -m compileall -q app`; suite backend completa
  en verde (RF-1…RF-9 verificados); marcar RF como implementados en `spec.md`
  y reportar.
