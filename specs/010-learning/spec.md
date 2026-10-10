# Spec 010 — Learning: hipótesis, conocimiento validado y memoria auditable

Estado: implementada (T1-T7 completadas; aprobada por el propietario el 2026-10-09)
Depende de: 001 (decisiones/posiciones/closed trades), 005 (eventos + correlation_id), 007 (analista IA, recomendación-only), 009 (pestaña Consola y sistema de diseño del panel).
Fuentes: brief §3 (Vista C — hipótesis vs conocimiento), §17 (estados PROPOSED→… y rollback), §29 (persistencia: hypotheses, knowledge, strategy_versions), §35; talos `view_03_learning_and_memory`; diagnóstico §8 (roadmap fase 9 → 010) y §16.6.

## Contexto

El brief exige una diferencia estricta entre lo que el sistema *sospecha* (hipótesis) y lo que ha *superado criterios estadísticos* (conocimiento confirmado), con memoria auditable y sin "machine learning mágico" (§3). Hoy no existe nada equivalente: no hay tablas de hipótesis/conocimiento, ni máquina de estados de aprendizaje, ni pestaña Learning (diagnóstico §7: ❌ en §17). La 009 dejó la pestaña Learning fuera de alcance a propósito. Esta spec construye el núcleo de memoria auditable; la *aplicación automática* de cambios al bot sigue prohibida (constitución #4 y §17: "no permitir que el sistema se auto-modifique").

## Decisiones de diseño

- **D-1** · Spec única: modelo + evaluación + API + pestaña Learning (dos columnas del talos view_03) en una sola spec, por bloques backend → frontend → validación.
- **D-2** · Creación de hipótesis: solo operador autenticado (`API_TOKEN`, patrón 001 RF-20) vía API. El campo `source` (`operator|ai`) queda reservado para futuras propuestas del analista IA; **este spec no modifica el esquema 007 ni deja al LLM crear hipótesis directamente** (aislamiento 007 RF-5 intacto).
- **D-3** · Máquina de estados (§17), única fuente de verdad:
  `PROPOSED → TESTING → VALIDATED → ACTIVE → DEPRECATED`, con `REJECTED` alcanzable desde `PROPOSED` y `TESTING`. Toda transición es explícita (endpoint) y emite evento 005; **`VALIDATED → ACTIVE` solo manual, jamás automática** (§17, principio del talos).
- **D-4** · Criterios estadísticos configurables (D-5) evaluados por un servicio determinista que cruza la hipótesis con closed trades/decisions ya persistidos (001); sin datos suficientes ⇒ la hipótesis permanece en `TESTING` con motivo visible, nunca pasa de estado sola hacia `ACTIVE`.
- **D-5** · Umbrales por defecto: `LEARNING_MIN_CASES=30` casos evaluables, `LEARNING_MIN_FAVORABLE_RATIO=0.60`, ventana por defecto 90 días (`LEARNING_WINDOW_DAYS`); confianza = ratio favorable (Decimal); intervalo de confianza Wald (z=1.96) "cuando sea aplicable" (n>0).
- **D-6** · `strategy_versions` (§17/§29) como registro **append-only** de cambios de parámetros con evidencia enlazada (hipótesis/conocimiento), backtest/paper referenciados como texto y rollback marcado; **la aplicación de una versión es siempre manual** (hoy: env/config de 001); el registro no toca el loop.
- **D-7** · Conocimiento `ACTIVE` en este spec es **consultable y visible** (API + UI); su inyección en el contexto del analista IA (007) queda para una spec futura para no tocar el servicio congelado de 007.
- **D-8** · Transporte y UI: polling ≤5 s (patrón 009), sin SSE/WebSocket, sin dependencias nuevas; interfaz en español; acentos con tokens existentes (`--orange` para hipótesis/ámbar, `--positive` para conocimiento/verde); tests de diseño extendidos, no relajados.
- **D-9** · Tres tablas nuevas (`hypotheses`, `knowledge`, `strategy_versions`), permitidas explícitamente por §29 y por el roadmap; nada de embeddings ni modelos locales.

## Requisitos funcionales

**RF-1 · Modelo de hipótesis (§3, §17).** Tabla `hypotheses`: `id`, `statement` (texto de la hipótesis), `origin_data_json` (datos que la originaron), `case_count`, `favorable_cases`, `unfavorable_cases`, `confidence` (Decimal, texto en API), `observed_period_start/finish`, `assets_json`, `market_regime`, `status` (`PROPOSED|TESTING|VALIDATED|ACTIVE|DEPRECATED|REJECTED`), `version` (entero, incrementa en cada transición de contenido), `source` (`operator|ai`), `rejection_reason`, `created_at`, `updated_at`. API en español con decimales como texto (patrón `_decimal_text`).

**RF-2 · Evaluación estadística determinista.** `evaluate_hypothesis(db, hypothesis_id, now)` cruza la hipótesis (activos + ventana + régimen declarados) con las decisiones cerradas (`SignalDecision` CLOSED con `pnl_usd`) ya persistidas: casos evaluables, favorables (pnl>0), desfavorables (pnl≤0), confianza y Wald; actualiza contadores y `updated_at`. Reglas:
- Si `status != TESTING` ⇒ 409 con motivo (solo se evalúa en TESTING).
- Si casos evaluables < `LEARNING_MIN_CASES` ⇒ se actualizan contadores y permanece `TESTING` con `evaluation_note` ("muestra insuficiente: N/M").
- Si ratio ≥ `LEARNING_MIN_FAVORABLE_RATIO` ⇒ transición automática a `VALIDATED` (evento `hypothesis.validated`); por debajo ⇒ permanece `TESTING` con nota (nunca `REJECTED` automático: el rechazo es manual).
- Mismo input ⇒ mismo output; sin red; Decimal en todos los cálculos.

**RF-3 · Conocimiento confirmado y rollback (§3).** Tabla `knowledge`: `id`, `hypothesis_id` (FK, nullable para conocimiento manual), `statement`, `evidence_json`, `sample_size`, `confidence_interval_json` (cuando aplique), `works_when_json`, `fails_when_json`, `validated_at`, `version`, `observed_impact`, `status` (`ACTIVE|DEPRECATED`), `rollback_reason`, `deprecated_at`, `created_at`. Reglas:
- La transición `VALIDATED → ACTIVE` de una hipótesis crea su fila de conocimiento (copia de evidencia) y emite `knowledge.promoted`; es **manual** (D-3).
- Rollback: `ACTIVE → DEPRECATED` con motivo obligatorio ⇒ evento `knowledge.rolled_back`; la fila se conserva (append-only, nunca se borra).
- `knowledge.older`/versiones: cada promoción incrementa `version`; un conocimiento degradado no puede volver a `ACTIVE` sin una nueva hipótesis validada.

**RF-4 · API de learning (autenticada con `API_TOKEN`).**
- `GET /api/learning/hypotheses?status=&limit=` → lista con todos los campos (RF-1), decimales como texto.
- `POST /api/learning/hypotheses` → alta (`statement` obligatorio; el resto opcional con defaults honestos: contadores 0, status `PROPOSED`).
- `POST /api/learning/hypotheses/{id}/transition` → `{to, reason?}`; valida la máquina de estados (D-3); transiciones inválidas ⇒ 409; `to=ACTIVE` exige conocimiento derivado (se crea en la misma transición) y motivo.
- `POST /api/learning/hypotheses/{id}/evaluate` → ejecuta RF-2 y devuelve la hipótesis actualizada.
- `GET /api/learning/knowledge?status=` → lista (RF-3).
- `GET /api/learning/strategy-versions` y `POST /api/learning/strategy-versions` (RF-6).
- Sin token ⇒ 401 (patrón 001 RF-20); sin humo: nada de endpoints que modifiquen órdenes o riesgo.

**RF-5 · Invariante de no auto-modificación (§17, 007 RF-5).** Ningún servicio de learning importa ni invoca `bot_loop`, ejecución de órdenes, `risk_engine` de escritura ni `ai_advisor` de ejecución; ningún estado `ACTIVE` altera parámetros de trading por sí solo. Verificable por test de imports/aislamiento (patrón `test_ai_isolation.py`).

**RF-6 · Registro de versiones de estrategia (§17, §29).** Tabla `strategy_versions` append-only: `id`, `version`, `config_json`, `evidence_json` (ids de hipótesis/conocimiento), `backtest_ref` (texto, p. ej. nombre del split), `paper_results_ref`, `motive`, `rolled_back_at`, `rollback_reason`, `created_at`. `POST` registra una versión nueva; marcar rollback (`POST /{id}/rollback` con motivo) no altera config actual; el cambio real sigue siendo manual (D-6). Evento `strategy_version.registered`.

**RF-7 · Pestaña Learning (UI, talos view_03).** Pestaña "Learning" en el panel (junto a Consola): dos columnas — **"Lo que va aprendiendo"** (hipótesis, acento ámbar `--orange`: tipo `source`, statement, evidencia/nº de casos, confianza, estado, fecha, contador de casos faltantes = `max(0, LEARNING_MIN_CASES − case_count)` exponiendo el umbral activo) y **"Lo que ha aprendido"** (conocimiento, acento verde `--positive`: afirmación, evidencia, confianza/intervalo, fechas de supuesto/confirmación, nº de casos, efecto observado, rollback si existe). Estados vacíos honestos; timestamp visible; polling 5 s; sin animación sin evento (§35). Los botones de transición/evaluación de la pestaña llaman los endpoints reales de RF-4 (solo lectura + acciones autenticadas ya existentes en el panel).

**RF-8 · Auditoría en eventos 005 (§17).** Toda acción emite evento con `service="learning"`: `hypothesis.proposed`, `hypothesis.transitioned` (de→a + motivo), `hypothesis.evaluated` (muestras y ratio), `knowledge.promoted`, `knowledge.rolled_back`, `strategy_version.registered`; correlation_id propio por hipótesis cuando exista. Cero secretos en payloads.

**RF-9 · Integridad y suite intacta.** Sin red en tests (SQLite temporal + mocks); Decimal para confianzas, ratios e importes; sin dependencias nuevas en frontend/backend; 001-009 sin cambios funcionales (las tablas 001 solo se leen); `npm run lint`, `npm test`, ruff y `compileall` en verde.

## Requisitos no funcionales

- Backend: Python 3.14, Decimal, API con decimales como texto, timestamps ISO-8601 UTC, Pydantic v2.
- Frontend: React 19 + Vite, vitest + jsdom + testing-library, español en UI, tokens de `design.json` sin hex nuevos.
- Retención: como el resto de tablas de negocio (sin purga propia en este spec).

## Casos límite

1. Evaluar fuera de `TESTING` ⇒ 409 con motivo.
2. Muestra insuficiente ⇒ permanece `TESTING` con nota, sin error.
3. Transición inválida (p. ej. `PROPOSED → ACTIVE`, `DEPRECATED → ACTIVE`) ⇒ 409.
4. `ACTIVE` sin motivo ⇒ 422.
5. Hipótesis sin activos o sin ventana ⇒ evaluación solo sobre el universo declarado; sin declarar ⇒ "sin universo declarado" en la nota (nunca inventar activos).
6. Rollback sin motivo ⇒ 422; rollback dos veces ⇒ 409 (ya `DEPRECATED`).
7. Conocimiento manual sin hipótesis ⇒ permitido (`hypothesis_id` nulo) con evidencia obligatoria.
8. Sin hipótesis/conocimiento ⇒ UI con estados vacíos textuales, sin cards decorativas (§35).
9. Sin token en mutations ⇒ 401.

## Fuera de alcance

- Auto-aplicación de cambios al bot o a parámetros de riesgo (prohibida por §17 y RF-5).
- Inyección de conocimiento `ACTIVE` en el contexto del analista IA (spec futura; D-7).
- Propuestas de hipótesis generadas por el LLM en este spec (D-2; el campo `source` las anticipa).
- Walk-forward y backtest (specs propias: D-4 de 009 y agresividad).
- Embeddings, fine-tuning, modelos locales, "machine learning mágico" (§3).
- Borrado físico de hipótesis/conocimiento (append-only; solo estados).

## Mapeo RF → tests

| RF | Tests (backend: `cd backend; .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` · frontend: `cd frontend; npm test`) |
|----|----|
| RF-1 | `tests/test_learning_hypotheses.py::HypothesisModelTests` (modelo, defaults, máquina de estados) + `tests/test_learning_api.py::LearningEndpointsTests` (lista/alta) |
| RF-2 | `tests/test_learning_evaluate.py::EvaluateHypothesisTests` (cruce con trades, umbrales, Wald, Decimal, determinismo) |
| RF-3 | `tests/test_learning_knowledge.py::KnowledgeTests` (promoción manual, rollback, versiones, append-only) |
| RF-4 | `tests/test_learning_api.py::LearningAuthTests` y `::LearningEndpointsTests` (endpoints, máquina de estados, 401/409/422) |
| RF-5 | `tests/test_learning_isolation.py::LearningIsolationTests` (imports prohibidos, sin escritura en riesgo/ejecución) |
| RF-6 | `tests/test_learning_strategy_versions.py::StrategyVersionTests` (registro, rollback marcado, sin aplicación) |
| RF-7 | vitest `LearningTab.test.jsx` ("LearningTab (RF-7)"), `HypothesisCard.test.jsx` ("HypothesisCard (RF-7)"), `KnowledgeCard.test.jsx` ("KnowledgeCard (RF-7)") + `src/api/__tests__/learning.test.js` ("api learning (RF-4)") + integración `Simulation.test.jsx` + `designSystem.test.js`/`actionSystem.test.js` extendidos (acentos ámbar/verde con tokens) |
| RF-8 | aserciones de eventos en `HypothesisModelTests`, `EvaluateHypothesisTests`, `KnowledgeTests` y `StrategyVersionTests` (payload y service `learning`) |
| RF-9 | verificación estática en T7 (grep sin `EventSource\|WebSocket`, package.json/requirements intactos) + suites completas backend/frontend |

## Criterios de finalización

1. ✅ Los 9 RF implementados y verificados con su test en verde.
2. ✅ Máquina de estados completa probada (todas las transiciones legales e ilegales).
3. ✅ Evaluación determinista probada con ≥3 escenarios (muestra insuficiente, validada, rechazada manualmente).
4. ✅ `VALIDATED → ACTIVE` jamás alcanzable sin acción manual (test explícito).
5. ✅ Suite backend completa en verde + `npm run lint` + `npm test` + ruff + `compileall`.
6. ✅ `tasks.md` con todas las casillas marcadas y estado `implementada (T1-Tn completadas; aprobada por el propietario el <fecha>)`.
