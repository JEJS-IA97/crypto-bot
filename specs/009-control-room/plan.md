# Plan de implementación — Spec 009 (UI Control Room)

Estado: borrador (2026-10-07) · pendiente de aprobación junto a `spec.md`.

## Orden de integración

Backend primero (endpoints + servicios + tests `unittest`), luego frontend (componentes + vitest), luego documentación y validación cruzada. Nada toca los contratos de 001-008: se añaden funciones y rutas nuevas.

## 1. Backend

### M1 · `GET /api/bot/ai/stats` (RF-1)

- `app/services/ai_advisor_service.py`: función nueva `ai_stats(db, since)` → consultas 24 h, coste total (`SUM(cost_usd)`), latencia media (`AVG(latency_ms)`), desglose por `status`/`decision`, `generated_at`. Ceros explícitos si no hay filas (caso límite 7). Solo lectura sobre `ai_evaluations`.
- `app/api/routes/ai.py`: `GET /api/bot/ai/stats` (sin token, igual que `/ai/recommendations`).
- Test: `tests/test_ai_stats_api.py` — fixture con 1-2 `AiEvaluation` (coste/latencia Decimal) → totales exactos; sin filas → ceros; coste devuelto como texto.

### M2 · `GET /api/bot/pipeline` (RF-2)

- `app/services/observability_service.py`: función nueva `pipeline_state(db, now)` → lista de nodos del catálogo.
- **Catálogo fijo** (backing exacto):

| kind | nodos (brief §13) | backing |
|---|---|---|
| source | MARKET DATA | `binance_klines`, `binance_ticker` (peor estado) |
| source | EXCHANGE | `binance_exchange_info` |
| source | ORDER BOOK | `binance_depth` |
| source | MACRO | `fear_greed` |
| source | NEWS | `news_rss` |
| source | AI ANALYST | `gemini` (fuente) + servicio `ai_advisor` (peor) |
| source | MEMORY | `database` |
| pipeline | FEATURE ENGINE | servicio `bot_loop` (ciclos) |
| pipeline | CANDIDATE FILTER | servicio `candidate_service` |
| pipeline | RISK ENGINE | servicio `risk_engine` |
| pipeline | EXECUTION | servicios `bot_loop` (eventos `order.*`) y `order_lifecycle` |
| pipeline | POSITION | servicio `order_lifecycle` |
| stub | PORTFOLIO ANALYZER | — ⇒ `DISABLED` "sin componente propio (integrado en candidate_service)" |
| stub | REGIME DETECTOR | — ⇒ `DISABLED` "sin implementar" |
| stub | SENTIMENT | — ⇒ `DISABLED` "sin fuente" |
| stub | TRADES | — ⇒ `DISABLED` "sin fuente" |
| stub | DERIVATIVES / FUNDING / OPEN INTEREST / OPTIONS / DEX | — ⇒ `DISABLED` "sin fuente" |
| stub | LEARNING | — ⇒ `DISABLED` "pendiente de spec 010" |

- Reglas (como en la spec): fuentes → estado `source_health` (005) de sus fuentes **con registro** (peor de las que tienen fila; las sin fila no empeoran; ninguna con fila ⇒ `DISABLED` "sin registro de salud"); pipeline → último evento de su servicio: `ERROR` si `level=ERROR`, `DEGRADED` si `level=WARNING`, `STALE` si >300 s, `HEALTHY` en otro caso; sin eventos ⇒ `DISABLED` "sin actividad". `last_event` = evento más reciente con `service/event/result/latency_ms/correlation_id/created_at`. `EXECUTION` solo considera eventos `order.*` de `bot_loop`/`order_lifecycle` (un `cycle.completed` alimenta `FEATURE ENGINE`, no `EXECUTION`). Respuesta: `{"nodes": [...]}` **sin `generated_at`** para garantizar determinismo estricto.
- `app/api/routes/observability.py`: `GET /api/bot/pipeline` (sin token, junto a `/sources`).
- Test: `tests/test_pipeline_api.py` — catálogo completo (los 22 nodos, cada uno con estado válido y `reason` si `DISABLED`), fuente ERROR ⇒ peor estado, pipeline con WARNING/ERROR reciente, pipeline en reposo ⇒ `STALE`/`DISABLED`, sin filas de salud ⇒ `DISABLED` con motivo.

### M3 · `GET /api/bot/decisions/{id}/why` (RF-4) y `.../replay` (RF-5)

- Servicio nuevo `app/services/replay_service.py` (solo lectura; patrón de `decision_store` para leer correlation_id por `_decision_correlation(decision)` → `market_snapshot_json["correlation_id"]`):
  - `why_payload(db, decision)`: decisión + `factors.positive/negative` desde `supporting_factors`/`contradicting_factors` de `response_json` de la `ai_evaluations` de la correlation_id (nunca signos inventados) + `factors.indicators` = `snapshot["indicators"]` crudos (contexto neutral) + `ai` (decision/direction/confidence/model/latency_ms/cost_usd/risk_flags) + `risk` desde el evento `risk.evaluated` de la correlation_id (action/reason/requested_usd/allowed_usd/committed_usd/open_positions) + `outcome` desde la decisión; secciones sin dato → `unavailable` con nombres de sección estables `ai` | `risk` | `events` y motivo (p. ej. "sin correlation_id", "sin evaluación IA").
  - `replay_payload(db, decision)`: `decision` + `snapshot` (price, timestamp, indicators, candles, config) + `events` (por correlation_id ordenados por `created_at`) + `ai_evaluation` (más reciente) + `position` (fill/precios/estado/pnl desde la propia decisión) + `outcome` + `unavailable` (motivos: "sin correlation_id", "sin evaluación IA", "fuera de retención de eventos", "noticias: no persistido", "order book: no persistido", "derivados: no persistido").
- Rutas nuevas `app/api/routes/decisions.py` (`prefix=/api/bot`): `GET /decisions/{id}/why`, `GET /decisions/{id}/replay`; 404 si no existe; registrar en `main.py`.
- Tests: `tests/test_why_api.py` (factores presentes/ausentes, `unavailable`, 404) y `tests/test_replay_api.py` (dos llamadas idénticas ⇒ misma respuesta; orden temporal estricto; decisión sin correlation_id ⇒ secciones `unavailable`; decisión antigua sin eventos ⇒ `unavailable` "fuera de retención", sin error).

### M4 · Reglas transversales backend

- Decimales como texto (reutilizar patrón `_decimal_text` sin importarlo de 008 si eso rompe el acoplamiento — copia local mínima o `str()` en serialización).
- Timestamps ISO-8601 con `Z` (UTC). Sin red en tests (SQLite temporal + `httpx` mockeado, patrón `test_risk_api`).
- Las funciones nuevas de `ai_advisor_service`/`observability_service` no alteran ninguna función existente de 005/007 (RF-19/RF-21 intactos; la zona congelada de RF-21 son solo los ficheros legados OKX/arbitraje, no estos).

## 2. Frontend

### Nuevos módulos de API

- `frontend/src/api/observability.js`: `getPipeline()`, `getEvents(params)`, `getSources()`, `getObservability()`.
- `frontend/src/api/bot.js`: `getAiStats()`, `getDecisionWhy(id)`, `getDecisionReplay(id)`.

### Componentes (React 19, JSX, español, tokens de `design.json`, `var(--space-N)`, sin `!important`)

- `HeaderPanel` (RF-1): compone `/status` + `/metrics` + `/simulation/summary` + `/sources` + `ai/stats` con polling 5 s; mapa de estados honesto (D-5): fase `SIMULATION/TESTNET/LIVE`, `OPERANDO`/`PAUSADO`/`EMERGENCIA (breaker)`, reloj UTC, cifras con timestamp.
- `PipelineCanvas` (RF-2): grafo por capas (fuentes → pipeline → stub) con badge de estado, `title`/detail al clic (payload resumido), nodos `DISABLED` visibles con motivo. Sin imágenes decorativas: SVG/CSS puro con tokens.
- `EventStream` / "Recorrido" (RF-3): filas por evento con timestamp/fuente/latencia/resultado/correlation_id + resumen de payload; agrupación por `correlation_id` (función pura `groupByCorrelation` testeable); estados vacíos explícitos.
- `WhyPanel` (RF-4) y `ReplayView` (RF-5): secciones `factors/risk/outcome` y `snapshot/events/ai_evaluation/position`, pintando `unavailable` como estado visible con motivo (no como error).
- `Timeline` (RF-6): línea de tiempo desde `replay_payload`, accesible desde `TradeHistory`/`OpenPositions`.
- `EquityChart` (RF-7): marcadores por trade cerrado (`trades` ya en props) → `onSelectDecision(id)` → abre timeline/Why?; sin trades ⇒ sin marcadores.

### Tests frontend (vitest + testing-library, ubicación/convención de los tests de componentes existentes)

`HeaderPanel.test.jsx`, `PipelineCanvas.test.jsx`, `EventStream.test.jsx`, `WhyPanel.test.jsx`, `ReplayView.test.jsx`, `Timeline.test.jsx`, `EquityChart.markers.test.jsx` + extensión de `designSystem.test.js`/`actionSystem.test.js` (marcadores nuevos sin romper reglas; sin `!important`, sin hex sueltos, un solo verde de acción).

## 3. Validación (T8)

1. `cd backend; .\.venv\Scripts\python.exe -m ruff check .`
2. `cd backend; .\.venv\Scripts\python.exe -m compileall -q app`
3. `cd backend; .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` (n + 434 en verde)
4. `cd frontend; npm run lint` y `cd frontend; npm test`
5. Estática RF-9: grep sin `EventSource|WebSocket` en `frontend/src`; `frontend/package.json` sin dependencias nuevas.
6. Respuestas de ejemplo de los 4 endpoints (curl con backend local) en el reporte.

## Riesgos

- **Correlation_id ausente** en decisiones externas ⇒ ya previsto como `unavailable` (nunca 500).
- **Retención/purga de eventos** ⇒ `unavailable` "fuera de retención"; el replay no depende de eventos para su núcleo.
- **Fechas relativas** (ventana de 300 s) ⇒ tests con `now` fijado por inyección/parámetro, sin depender del reloj real.
- **Composición del header** ⇒ si un endpoint falla, el header muestra ese bloque como "sin datos" sin romper el resto (patrón `Promise.allSettled`).
