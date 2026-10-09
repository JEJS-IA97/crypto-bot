# Spec 009 — UI Control Room: canvas de nodos, Why?, replay

Estado: implementada (T1-T8 completadas; aprobada por el propietario el 2026-10-07)
Depende de: 003 (panel + sistema de diseño), 005 (eventos + source_health), 006 (candidatos), 007 (ai_evaluations), 008 (risk.evaluated); complementa 001 (decisiones/posiciones).
Fuentes: brief §2 (Vista B, 15 preguntas), §11 (replay), §12 (header/estados), §13 (canvas), §14 (eventos en vivo), §15 (Why?), §16 (operaciones/timeline), §35 (reglas de diseño), §37; diagnóstico §8 (roadmap: fases 8+10 → 009) y §16 (Plan de UI).

## Contexto

El panel actual (003) muestra métricas, kill switch, equity, posiciones e historial con polling de 5 s, pero solo consume `/api/bot/status`, `/api/bot/metrics`, `/api/signals/decisions` y `/simulation/*`. En backend ya existen datos ricos sin consumir en la UI: eventos con correlation_id (005), salud de fuentes, evaluaciones IA con coste (007), `risk.evaluated` (008), snapshot de indicadores por decisión (001). No existe endpoint de detalle/replay de decisiones ni de agregados de IA. La consola de inteligencia del brief (canvas de nodos reales, "Why?", replay de decisiones, recorrido de eventos) queda por construir.

## Decisiones de diseño

- **D-1** · Spec única con tareas por bloques (backend → frontend → validación). Decisión del propietario, 2026-10-07.
- **D-2** · El control de agresividad 1-10 (§12) queda FUERA de alcance; tendrá spec propia con mapping a parámetros reales. Decisión del propietario, 2026-10-07.
- **D-3** · Replay/Why? solo sobre datos YA persistidos (snapshot de la decisión, eventos 005 por correlation_id, `ai_evaluations`, decisiones y posiciones). Lo no guardado (noticias, order book, derivativos) se presenta como "no disponible" con motivo; sin tablas nuevas ni datos inventados (brief §5). Decisión del propietario, 2026-10-07.
- **D-4** · Walk-forward fuera de alcance (spec aparte). Decisión del propietario, 2026-10-07.
- **D-5** · Estados honestos: la UI solo pinta estados que existen en backend (fase `SIMULATION|TESTNET|LIVE`, `running`, `breaker_active`, estados de `source_health`). Las etiquetas del brief (OFFLINE/PAPER/SHADOW/LIVE; SOLO CIERRE/PAUSADO/OPERANDO/EMERGENCIA) se muestran como mapa sobre esos estados reales; SHADOW y SOLO CIERRE no existen y por tanto no se pintan como estados (§35).
- **D-6** · Catálogo fijo de nodos del canvas (los 22 del §13) con backing declarado: cada nodo apunta a fuente(s) de `source_health` y/o servicio(s) emisor(es) de eventos. Sin backing o sin registro ⇒ `DISABLED` con motivo explícito.
- **D-7** · Transporte: polling ≤5 s ya existente; SIN SSE/WebSocket y sin dependencias nuevas.
- **D-8** · Cuatro endpoints nuevos: `GET /api/bot/pipeline`, `GET /api/bot/ai/stats`, `GET /api/bot/decisions/{id}/why`, `GET /api/bot/decisions/{id}/replay`. El header se compone en cliente con endpoints existentes (`/status`, `/metrics`, `/sources`, `/observability`, `/simulation/summary`, `/api/signals/decisions`).
- **D-9** · Interfaz en español, tokens y sistema de acción de 003; tests de diseño (designSystem/actionSystem) extendidos, no relajados.
- **D-10** · Enlace equity→decisión (RF-7): `simulation_trades` no guardaba `decisión_id`. Se añade columna nullable `decision_id` (indexada) poblada desde el bot en `protection_after_fill` (entrada) y `close_position` (salida) vía `link_fill_to_decision` (usa `raw.simulation_trade_id` del fill del simulador), expuesta en `TradeResponse`/`TradeHistoryResponse`. Los trades manuales o sin enlace quedan con `decision_id` nulo y sin marcador clicable. Decisión del propietario, 2026-10-07.

## Requisitos funcionales

**RF-1 · Header en vivo con datos reales (§12).** El header global de la consola mostrará: fase y estado operativo (fase real + `OPERANDO` si `running`, `PAUSADO` si kill switch, `EMERGENCIA` si `breaker_active`), reloj UTC, capital (balance), PnL diario y PnL total, drawdown, operaciones abiertas y cerradas, consultas IA (24 h), coste IA (24 h), latencia media IA y resumen de salud de fuentes. Cada cifra con su timestamp de última actualización y procedente de endpoints reales; para la IA usa `GET /api/bot/ai/stats` (nuevo).

**RF-2 · Canvas de nodos del pipeline (§13).** `GET /api/bot/pipeline` devuelve el catálogo fijo de nodos con: `id`, `label`, `kind` (`source|pipeline|stub`), `state` (`HEALTHY|DEGRADED|STALE|ERROR|DISABLED`), `backing` (fuentes/servicios), `last_update`, `reason` (obligatorio si `DISABLED`) y `last_event` (`service`, `event`, `result`, `latency_ms`, `correlation_id`, `created_at`) cuando exista. Reglas de estado:
- Nodo-fuente: hereda el estado de `source_health` (005) de sus fuentes; con varias fuentes, el peor estado; sin registro ⇒ `DISABLED` ("sin registro de salud").
- Nodo-pipeline: último evento de su servicio; `ERROR` si `level=ERROR`, `DEGRADED` si `level=WARNING`, `STALE` si el más reciente tiene >300 s, `HEALTHY` en otro caso; sin eventos nunca ⇒ `DISABLED` ("sin actividad").
- Nodos `stub` (sin componente implementado) ⇒ `DISABLED` con motivo (p. ej. "sin fuente", "pendiente de spec 010").
Catálogo: EXCHANGE, MARKET DATA, ORDER BOOK, TRADES, DERIVATIVES, FUNDING, OPEN INTEREST, OPTIONS, DEX, NEWS, MACRO, SENTIMENT, FEATURE ENGINE, REGIME DETECTOR, CANDIDATE FILTER, PORTFOLIO ANALYZER, AI ANALYST, RISK ENGINE, EXECUTION, POSITION, LEARNING, MEMORY (backing exacto en el plan).
El clic en un nodo abre su payload resumido (último evento + latencia + correlation_id + fuentes con su estado).

**RF-3 · Recorrido de eventos en vivo (§14).** Componente que, dado un correlation_id (o "últimos ciclos"), lista la secuencia real de eventos (`GET /api/bot/events?correlation_id=`) ordenada por `created_at` con timestamp, fuente, latencia, resultado, correlation_id y resumen de payload. Las etapas del brief (señal → riesgo → IA → envío → fill → posición → resultado) se muestran SOLO cuando existe el evento correspondiente (`decision.emitted`, `risk.evaluated`, `ai.consultation`, `order.sent`, `order.filled`, `order.failed`, `decision.blocked`, `cycle.completed`). Sin eventos ⇒ "sin actividad registrada"; prohibida toda animación sin evento real (§35).

**RF-4 · Panel "Why?" (§15).** `GET /api/bot/decisions/{id}/why` devuelve: decisión (símbolo, lado, estado, cantidad, precios, pnl, rejection_reason, `created_at`), `factors` (positivos/negativos desde `supporting_factors`/`contradicting_factors` de la `ai_evaluations` de la correlation_id, más los `indicators` del snapshot expuestos crudos — nunca signos inventados), `risk` (del evento `risk.evaluated` de la correlation_id: razón, límites), `ai`, `outcome` y `unavailable` (nombre de sección `ai|risk|events` + motivo). Cada sección sin datos persistidos va en `unavailable`; nunca texto generado ni interpretaciones libres.

**RF-5 · Vista de replay (§11).** `GET /api/bot/decisions/{id}/replay` devuelve la reconstrucción determinista de la decisión en su instante: `decision`, `snapshot` (price, timestamp, indicators, candles, config), `events` (por correlation_id, ordenados), `ai_evaluation`, `position` (fill, stop, take-profit, estado, pnl si existe), `outcome` y `unavailable` (secciones no persistidas, p. ej. "noticias: no persistido"; "eventos: fuera de retención"). Misma decisión ⇒ misma respuesta. Decisión inexistente ⇒ 404.

**RF-6 · Timeline de operación (§16).** Desde historial/posiciones, cada operación abre su línea de tiempo (decisión → eventos correlacionados → fills → cierre → pnl), reutilizando el payload de replay; campos: orden temporal, timestamps UTC y resultado.

**RF-7 · Equity con marcadores seleccionables.** La gráfica de equity incorpora un marcador por operación cerrada; al seleccionarlo se abre el timeline/Why? de esa decisión. Sin operaciones ⇒ sin marcadores.

**RF-8 · Sin humo testeable (§35).** Ninguna cifra sin timestamp y fuente; todo estado `DISABLED` con motivo; los botones nuevos llaman endpoints reales; prohibidos: imágenes decorativas, "thinking" falso, métricas sin timestamp y animación sin evento. Verificable por tests de componentes y tests de diseño/acción extendidos.

**RF-9 · Aislamiento y suite intacta.** Sin SSE/WebSocket ni dependencias nuevas en `frontend/package.json`; polling ≤5 s; tests sin red; backend intacto (001-008 sin cambios funcionales); todo el backend en Decimal para valores monetarios.

## Requisitos no funcionales

- Backend: Python 3.14, Decimal para dinero, API con decimales como texto (patrón `_decimal_text`), timestamps ISO-8601 UTC.
- Frontend: React 19 + Vite (JSX), vitest + jsdom + testing-library, eslint; español en UI; tokens de `design.json`; `designSystem.test.js` y `actionSystem.test.js` en verde.
- Sin red en tests (backend: SQLite temporal; frontend: mocks de módulos/axios).

## Casos límite

1. Decisión sin `ai_evaluations` ⇒ sección IA en `unavailable` ("sin evaluación IA").
2. Decisión sin `correlation_id` en su snapshot (señales externas) ⇒ secciones de eventos/riesgo/IA en `unavailable` ("sin correlation_id").
3. Decisión más antigua que la retención de eventos ⇒ `unavailable` ("fuera de retención de eventos"), sin 500.
4. Decisión inexistente ⇒ 404.
5. Fuente sin fila en `source_health` ⇒ nodo `DISABLED` con motivo.
6. Breaker activo ⇒ header `EMERGENCIA` (breaker) y canvas sin cambios (el breaker es runtime, no fuente).
7. Sin consultas IA en 24 h ⇒ stats con ceros y "sin consultas" explícito, no NaN.
8. Equity sin trades cerrados ⇒ sin marcadores.
9. Payload de evento ausente/vacío ⇒ fila igual con "sin payload" (nunca payload inventado).

## Fuera de alcance

- Control de agresividad 1-10 (spec propia posterior; decisión D-2).
- Walk-forward (spec aparte; decisión D-4).
- Pestaña Learning (requiere spec 010).
- Modos SHADOW / SOLO CIERRE / OFFLINE como estados (no existen en backend; decisiones D-5 y fases futuras).
- SSE/WebSocket, nuevas dependencias, nuevas tablas o campos persistidos.
- Replay con datos externos no persistidos (noticias, order book, derivados) — solo se declaran `unavailable` (D-3).
- Tocar contratos congelados de 001-008 (`risk_service`, `bot_loop` de 008, `ai_advisor_service` de 007 salvo función auxiliar nueva sin cambiar RF-19/RF-21).

## Mapeo RF → tests

| RF | Tests (backend: `cd backend; .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` · frontend: `cd frontend; npm test`) |
|----|----|
| RF-1 | `tests/test_ai_stats_api.py` (`AiStatsApiTests`) + vitest `HeaderPanel.test.jsx` |
| RF-2 | `tests/test_pipeline_api.py` (`PipelineApiTests`: catálogo completo, reglas de estado, DISABLED con motivo) + vitest `PipelineCanvas.test.jsx` |
| RF-3 | vitest `EventStream.test.jsx` (orden, etapas solo con evento real, estado vacío) |
| RF-4 | `tests/test_why_api.py` (`WhyApiTests`: factores desde snapshot+IA+risk, `unavailable`) + vitest `WhyPanel.test.jsx` + `DecisionInspector.test.jsx` |
| RF-5 | `tests/test_replay_api.py` (`ReplayApiTests`: determinismo, orden, 404, fuera de retención) + vitest `ReplayView.test.jsx` + `DecisionInspector.test.jsx` |
| RF-6 | vitest `Timeline.test.jsx` (orden temporal, reutiliza payload) + `DecisionInspector.test.jsx` + integración en `Simulation.test.jsx` |
| RF-7 | `tests/test_trade_decision_link.py` (`TradeDecisionLinkTests`: entrada/salida enlazadas, manual sin enlace, `TradeResponse`/`TradeHistoryResponse`) + vitest `EquityChart.markers.test.jsx` + integración en `Simulation.test.jsx` |
| RF-8 | `frontend/src/test/designSystem.test.js` (marcadores con tokens, sin hex sueltos) y `actionSystem.test.js` (marcadores sin tonos de acción) + aserciones de timestamp/fuente/motivo en tests de componentes |
| RF-9 | verificación estática en T8 (grep sin `EventSource|WebSocket`, `package.json` sin dependencias nuevas, polling a 5 s) + suite backend completa |

## Criterios de finalización

1. ✅ Los 9 RF implementados y verificados con su test en verde.
2. ✅ Los 4 endpoints nuevos (`ai/stats`, `pipeline`, `decisions/{id}/why`, `decisions/{id}/replay`) probados con `httpx` mockeado (sin red).
3. ✅ Suite backend completa en verde: **468 tests OK** (los de 001-008 intactos + los de 009).
4. ✅ `npm run lint` y `npm test` (**23 suites / 107 tests**) en verde; `ruff check` y `compileall` en verde.
5. ✅ `tasks.md` con todas las casillas marcadas y estado `implementada`.
