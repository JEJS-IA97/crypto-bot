# Spec 005 — Observabilidad estructurada

Estado: **implementada (T1-T7), aprobada por el propietario el 2026-10-07**;
suite backend completa en verde (279 tests) + `ruff` limpio.
Relación: complementa `specs/001-bot-binance-spot` **sin modificar su comportamiento**
(los 252 tests de 001 deben seguir verdes). Fuente: `docs/fase0-diagnostico-brief-ia.md`
§14 + brief §27/§13/§29. No depende de las decisiones D-B1…D-B4 (specs futuras);
D-B5 (este orden) queda aprobada con este documento.

## Contexto

Hoy hay 8 loggers puntuales (`bot_loop`, `binance_executor`, `order_lifecycle`,
`keepalive_service`), métricas de negocio en `/api/bot/metrics` y `/health`, pero:
sin formato estructurado, sin correlation ID que una decisiones con sus logs, sin
estado de salud de las fuentes (Binance, BD), sin eventos persistidos y sin
métricas técnicas. Eso bloquea el control room (spec 009) y el replay (brief §11).

## Decisiones de diseño

- **D-1 · Tablas nuevas, cero ALTER**: solo `system_events` y `source_health`
  (creadas por `Base.metadata.create_all`). El `correlation_id` de cada decisión se
  guarda **dentro** de `SignalDecision.snapshot` (JSON ya existente) → sin migración.
- **D-2 · JSON por línea a stdout** con `logging` de stdlib (Render captura stdout).
  Sin dependencias nuevas (constitución #12).
- **D-3 · Fail-open**: un fallo del logger o de la persistencia de eventos **nunca**
  interrumpe el ciclo de trading ni cambia una decisión (mismo patrón que
  `record_cycle_failure` en `bot_loop.py:640-643`).
- **D-4 · Sin UI**: lectura solo por API REST; la consola llega en la spec 009.
- **D-5 · Retención por edad**: purga al arrancar y como máximo cada 24 h.
- **D-6 · Estados de fuente** del brief §13: `HEALTHY | DEGRADED | STALE | ERROR | DISABLED`.
- **D-7 · Sin secretos**: payload con allowlist/campos prohibidos (`api_key`,
  `token`, `secret`, `pass`, `authorization`…), testeable.
- **D-8 · Versiones en eventos**: `mode` = fase activa actual (o `unknown`);
  `strategy_version` desde `settings` (env con defecto).

## Requisitos funcionales

- **RF-1 — Evento estructurado en stdout.** MIENTRAS el sistema opere, CADA
  evento observable (ciclo, decisión, orden, fallo de fuente, fase) SE registra como
  una línea JSON con, al menos: `timestamp` (UTC ISO 8601), `level`, `service`,
  `event`, `mode`, `result`; y CUANDO aplique: `correlation_id`, `asset`,
  `latency_ms`, `strategy_version`. Si el registro falla, EL SISTEMA continúa el
  ciclo igual (fail-open, D-3).

- **RF-2 — Correlation ID por ciclo.** CADA ciclo de evaluación genera un
  `correlation_id` (UUID4) que SE asocia a todas las decisiones y eventos de ese
  ciclo; CADA `SignalDecision` lo persiste dentro de su campo `snapshot`.

- **RF-3 — Eventos persistidos.** EL SISTEMA persiste cada evento observable en la
  tabla `system_events` con: `created_at`, `level`, `service`, `event`, `asset`
  (nullable), `correlation_id` (nullable), `mode`, `latency_ms` (nullable),
  `result` y `payload_json` (resumen ≤ 4 KB).

- **RF-4 — Cero secretos.** NINGÚN log ni `payload_json` puede contener claves,
  tokens ni contraseñas: los valores de campos prohibidos SE redactan como
  `[REDACTED]` antes de emitirse.

- **RF-5 — Salud de fuentes.** EL SISTEMA mantiene el estado de las fuentes que ya
  consume (klines/exchangeInfo/ticker de Binance, base de datos) con
  `state`, `last_success_at`, `last_error` y `updated_at`, y lo expone en
  `GET /api/bot/sources`. Una fuente sin éxito reciente SE marca `STALE`; una
  fuente caída `ERROR`; una fuente no configurada `DISABLED`.

- **RF-6 — Consulta de eventos.** `GET /api/bot/events` DEVUELVE los eventos más
  recientes con filtros opcionales (`level`, `asset`, `correlation_id`) y `limit`
  (defecto 50, máximo 200), orden descendente por `created_at`, sin secretos.

- **RF-7 — Métricas técnicas.** `GET /api/bot/observability` DEVUELVE agregados de
  las últimas 24 h calculados sobre `system_events`: conteo de eventos por nivel,
  resultado de los ciclos (`ok|failed|…`), último error registrado y resumen de
  salud de fuentes (conteo por estado).

- **RF-8 — Retención de eventos.** EL SISTEMA elimina los eventos con `created_at`
  más antiguo que `EVENT_RETENTION_DAYS` (defecto 30) al arrancar y después como
  máximo una vez cada 24 h; la purga con tabla vacía ES no-op.

- **RF-9 — Cero cambio de comportamiento.** LA instrumentación no altera
  decisiones, órdenes ni estados: la suite completa de la spec 001 sigue verde sin
  modificar ninguna aserción existente.

## Requisitos no funcionales

- **RNF-1 — Sin dependencias nuevas** (stdlib `logging`/`json`/`uuid`).
- **RNF-2 — Escritura acotada**: payload truncado a 4 KB; la persistencia de un
  evento usa la sesión existente del ciclo (sin transacciones nuevas por evento).
- **RNF-3 — Suite sin red ni credenciales**: eventos se prueban con SQLite en
  memoria y logger capturado (mock/`assertLogs`, patrón RNF-2 de 001).
- **RNF-4 — Zona congelada intacta** (RF-21): ningún fichero de la lista de
  congelación se modifica.

## Casos límite

1. Fallo al persistir evento → se emite igual a stdout y el ciclo continúa (D-3).
2. Payload > 4 KB → se trunca con marca `truncated=true`.
3. Evento de arranque/parada sin ciclo → `correlation_id: null` (nullable).
4. Fuente nunca usada → fila `DISABLED` o `STALE` según configuración.
5. Payload que accidentalmente contiene un secreto → `[REDACTED]` (RF-4).
6. `GET /api/bot/events` con tabla vacía → lista vacía, HTTP 200.
7. `limit` fuera de rango → se clampa a [1, 200].

## Fuera de alcance

- UI/canvas de nodos, panel "Why?", replay visual → spec 009.
- Adaptadores de datos nuevos (noticias, derivados), feature/candidate engine → 006.
- Cualquier LLM (Gemini), coste IA → 007.
- Cambios en lógica de trading, riesgo o ejecución → prohibido (RF-9).
- VPS/redis/rate limiting → specs posteriores.

## Estado de implementación (2026-10-07)

| RF | Verificado por |
|---|---|
| RF-1 | `test_observability.py::StructuredLogTests` (4 tests, incl. fail-open) |
| RF-2 | `test_observability.py::CorrelationIdTests` (2 tests con `run_once` real) |
| RF-3 | `test_observability.py::EventPersistenceTests` (3 tests, incl. truncado 4 KB) |
| RF-4 | `test_observability.py::RedactionTests` (3 tests) |
| RF-5 | `test_observability.py::SourceHealthTests` (3) + `test_observability_api.py::SourcesEndpointTests` |
| RF-6 | `test_observability_api.py::EventsEndpointTests` (5) |
| RF-7 | `test_observability.py::AggregatesTests` + `test_observability_api.py::ObservabilityEndpointTests` (2) |
| RF-8 | `test_observability.py::RetentionTests` (2) + purga en lifespan/loop |
| RF-9 | Suite completa 279 OK sin modificar ninguna aserción de las specs 001-004 |

## Criterios de finalización

1. ✅ RF-1…RF-9 con test rojo→verde y mapeados en `plan.md`.
2. ✅ Suite backend completa en verde (252 existentes + 27 nuevos) + `ruff check` limpio.
3. ✅ `test_models_new_tables.py` extendido con las tablas nuevas; ficheros congelados
   sin tocar.
4. ✅ `.env.example` y `backend/README.md` actualizados (EVENT_RETENTION_DAYS,
   LOG_LEVEL, STRATEGY_VERSION, endpoints nuevos).
5. Aprobación explícita del usuario antes de cualquier paso de la siguiente spec.
