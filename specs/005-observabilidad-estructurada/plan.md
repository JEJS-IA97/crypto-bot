# Plan — Spec 005 (Observabilidad estructurada)

Ver `spec.md`. Convenciones del repo: `Decimal` para dinero (aqui no aplica), código
en inglés, mensajes de UI/docs en español, TDD, sin dependencias nuevas.

## Módulos

| # | Módulo | Qué | RF |
|---|---|---|---|
| M1 | `app/models.py` | `SystemEvent` (`system_events`) y `SourceHealth` (`source_health`), tablas nuevas | RF-3, RF-5 |
| M2 | `app/config.py` + `.env.example` | `event_retention_days=30`, `log_level="INFO"`, `strategy_version="orb-001-v3"` | RF-8, RF-1 |
| M3 | `app/services/structured_log.py` | `JsonFormatter` (campos obligatorios), `configure_logging()` para el lifespan, `redact(obj)` con campos prohibidos (RF-4) y `emit(...)` **fail-open** que loguea a stdout y delega la persistencia | RF-1, RF-4 |
| M4 | `app/services/observability_service.py` | `record_event(db, …)` (payload truncado 4 KB), `mark_source(db, name, ok/error)`, `sources_state(db)` (deriva STALE/DISABLED), `purge_old_events(db, now)` y `aggregates_24h(db)` | RF-3, RF-5, RF-7, RF-8 |
| M5 | `app/services/bot_loop.py` | Generar `correlation_id` al inicio de `run_once` (`bot_loop.py:603`), evento `cycle.completed` con status/opened/closed/rejected/error y latencia, inyectarlo en los `snapshot` de decisión y marcar fuentes en los puntos de fallo ya existentes (`except` de klines/breaker) | RF-2, RF-1, RF-9 |
| M6 | `app/services/order_lifecycle.py` y `binance_executor.py` | Eventos `order.sent/filled/failed` reutilizando los `logger` ya existentes (solo añadir `emit`, no reescribir) | RF-1, RF-9 |
| M7 | `app/api/routes/observability.py` + `main.py` | Rutas `GET /api/bot/events`, `GET /api/bot/sources`, `GET /api/bot/observability` (solo lectura → sin token, RF-20 de 001); registrar router y `configure_logging()` + purga inicial en el lifespan | RF-5, RF-6, RF-7 |
| M8 | `app/services/bot_loop.py` / rutas de fase | Eventos `phase.changed` y `system.started/stopped` (donde ya se escribe `BotPhase`) | RF-1 |

## Modelo de datos (tablas nuevas)

```text
system_events
  id             INTEGER PK
  created_at     DATETIME NOT NULL, indexado
  level          VARCHAR(10)   -- INFO/WARNING/ERROR
  service        VARCHAR(50)   -- bot_loop / execution / api …
  event          VARCHAR(60)   -- cycle.completed, order.sent, source.error …
  asset          VARCHAR(12)   -- nullable (BTCUSDT)
  correlation_id VARCHAR(36)   -- nullable (UUID4), indexado
  mode           VARCHAR(20)   -- SIMULATION/TESTNET/LIVE/unknown
  latency_ms     INTEGER       -- nullable
  result         VARCHAR(20)   -- ok/failed/blocked/…
  payload_json   TEXT          -- resumen ≤ 4 KB, redactado (RF-4)

source_health
  name            VARCHAR(50) PK   -- binance_klines / binance_ticker / database
  state           VARCHAR(12)      -- HEALTHY|DEGRADED|STALE|ERROR|DISABLED
  last_success_at DATETIME nullable
  last_error      VARCHAR(200) nullable
  updated_at      DATETIME NOT NULL
```

Sin columnas nuevas en tablas existentes (D-1); `SignalDecision.snapshot` ya es
JSON y recibe la clave `correlation_id`.

## Eventos mínimos (inventario)

`system.started`, `system.stopped`, `phase.changed`, `cycle.completed`,
`decision.emitted`, `decision.blocked`, `order.sent`, `order.filled`,
`order.failed`, `source.error`.

## RF → test (mapeo obligatorio)

| RF | Fichero de test | Clase/prueba |
|---|---|---|
| RF-1 | `tests/test_observability.py` | `StructuredLogTests` (JSON por línea + campos obligatorios + fail-open) |
| RF-2 | `tests/test_observability.py` | `CorrelationIdTests` (UUID por ciclo → `snapshot`) |
| RF-3 | `tests/test_observability.py` | `EventPersistenceTests` (columnas + truncado 4 KB) |
| RF-4 | `tests/test_observability.py` | `RedactionTests` (api_key/token/secret → `[REDACTED]`) |
| RF-5 | `tests/test_observability.py` | `SourceHealthTests` (transiciones + STALE/DISABLED) |
| RF-6 | `tests/test_observability_api.py` | `EventsEndpointTests` (filtros, clamps, 200 con vacío) |
| RF-7 | `tests/test_observability_api.py` | `ObservabilityEndpointTests` (agregados 24 h) |
| RF-8 | `tests/test_observability.py` | `RetentionTests` (purga + no-op) |
| RF-9 | suite completa | Los 252 tests de 001/002/003/004 sin cambios de aserción + `test_models_new_tables` extendido |

## Orden de implementación (rojo → verde)

T1 tests rojos (RF-1…RF-8) → T2 modelos+config → T3 structured_log →
T4 observability_service → T5 instrumentación de bot_loop/órdenes → T6 API+main →
T7 docs + validación final. Detalle en `tasks.md`.

## Riesgos y mitigación

- **Cero cambio de comportamiento (RF-9)**: la instrumentación se añade al final de
  cada bloque y dentro de `try/except` (patrón ya usado en `run_once`); si un test
  existente falla, se corrige la instrumentación, nunca la aserción.
- **Rendimiento**: un INSERT por evento en la sesión del ciclo (sin commit extra);
  si la BD falla, se degrada a solo stdout (D-3).
- **Neon/SQLite**: tablas nuevas por `create_all` funcionan en ambos (mismo
  patrón que `test_models_new_tables.py`).
