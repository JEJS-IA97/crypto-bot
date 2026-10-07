# Plan — Spec 007 (Analista IA, Gemini)

Ver `spec.md`. TDD estricto, `Decimal` en dominio, código e identificadores
en inglés, docs/mensajes en español. Ningún módulo de esta spec se importa
desde el loop de la 001 (D-1/RF-5).

## Módulos

| # | Módulo | Qué | RF |
|---|---|---|---|
| M1 | `app/config.py` | `gemini_api_key=""`, `gemini_model="gemini-2.5-flash"`, `gemini_base_url="https://generativelanguage.googleapis.com/v1beta"`, `gemini_timeout_seconds=10`, `gemini_max_retries=2`, `gemini_daily_query_limit=4`, `gemini_cache_seconds=3600`, `gemini_breaker_failures=3`, `gemini_breaker_seconds=900`, `gemini_auto_analysis=false`, `gemini_auto_analysis_limit=3`, `gemini_daily_budget_usd=0`, `gemini_price_mtok_input=0`, `gemini_price_mtok_output=0` | RF-3, RF-4, RF-8 |
| M2 | `app/domain/ai_schema.py` | Pydantic v2 `AdvisorResponse` estricto (`extra="forbid"`, `decision: BUY\|SELL\|WAIT`, `direction: LONG\|NEUTRAL`, `confidence/setup_quality: Decimal 0..1`, listas de factores/flags/invalidaciones, zonas `str\|None`, `reason_codes`, `required_next_check`, `data_quality`) + `from_json()` que lanza `SchemaViolation` | RF-2 |
| M3 | `app/services/gemini_client.py` | `GeminiClient.generate(prompt, *, request_id) -> GeminiReply(text, input_tokens, output_tokens, model, request_id, latency_ms)`; POST `{base}/models/{model}:generateContent` con `x-goog-api-key` en cabecera, `responseMimeType: application/json`, timeout, ≤2 reintentos solo ante timeout/5xx (nunca 429 ⇒ `GeminiQuotaExceeded`), errores `GeminiUnavailable` sin claves en el mensaje | RF-3, RF-4 |
| M4 | `app/services/ai_advisor_service.py` | `analyze(symbol, *, db, now=None, market_data=None, client=None, force=False) -> AnalysisOutcome(state, evaluation, cached)`: guarda DISABLED → breaker → presupuesto → cuota → caché → contexto (006 `get_context` + klines/features/score + `PositionV2` abiertas + `DailyRiskState` + límites) → prompt (`PROMPT_VERSION`) → cliente → esquema → fila `ai_evaluations` → evento `ai.consultation` + `mark_source("gemini")`; contadores y breaker en memoria con `reset_state()` para tests | RF-1, RF-3, RF-4, RF-6 |
| M5 | `app/models.py` | Tabla `ai_evaluations`: `id, created_at, symbol, trigger(manual\|auto), status(OK\|ERROR), decision, direction, confidence, request_id, correlation_id, model, prompt_version, latency_ms, input_tokens, output_tokens, cost_usd, context_json, response_json, error` | RF-6 |
| M6 | `app/api/routes/ai.py` + `main.py` | `POST /api/bot/ai/analyze` (body `{symbol, force?}`), `GET /api/bot/ai/recommendations?symbol=&limit=` (clamp 1…50, defecto 20); router registrado; sin token | RF-7 |
| M7 | `app/services/ai_daily_analysis.py` | `run_daily_pass(*, db, now, market_data=None, client=None) -> int`: tops de `candidate_service` (limit `gemini_auto_analysis_limit`) → `analyze` hasta estado no `OK`; pasa solo si la última evaluación `trigger=auto` tiene ≥24 h. Loop fino asyncio (intervalo 1 h) arrancado en el lifespan solo si `gemini_auto_analysis` y hay clave | RF-8 |
| M8 | eventos 005 | `ai.consultation` (INFO ok / WARNING degradado / ERROR fallo; payload: state, decision?, tokens, coste, latencia, model, prompt_version) + `gemini` añadido a `KNOWN_SOURCES` | RF-6 |
| M9 | `.env.example`, `backend/README.md` | Vars de Gemini, estados y endpoints | RF-7 |

## Modelos de dominio (Pydantic para I/O del LLM; `dataclass(frozen=True)` internos)

```text
AdvisorResponse (Pydantic, extra="forbid"):
  decision: BUY|SELL|WAIT
  direction: LONG|NEUTRAL                 (D-13: spot sin cortos)
  confidence, setup_quality: Decimal 0..1
  risk_flags, supporting_factors, contradicting_factors,
  invalidating_conditions, reason_codes: list[str]
  time_horizon: str
  suggested_entry_zone, suggested_stop_zone,
  suggested_take_profit_zone: str | None
  required_next_check: str
  data_quality: dict[str, str]

GeminiReply: text, input_tokens, output_tokens, model, request_id, latency_ms
AnalysisOutcome: state, evaluation (AiEvaluation | None), cached (bool)
states: OK | DISABLED | QUOTA_EXCEEDED | BUDGET_EXCEEDED | BREAKER_OPEN
        | INVALID_RESPONSE | ERROR
```

Fórmulas:

```text
coste_usd = (input_tokens · GEMINI_PRICE_MTOK_INPUT
           + output_tokens · GEMINI_PRICE_MTOK_OUTPUT) / 1_000_000   (Decimal, 6 dec.)
presupuesto: corta si coste estimado de la consulta > 0
             y coste acumulado del día >= GEMINI_DAILY_BUDGET_USD
cuota:      filas de ai_evaluations con created_at >= inicio del día UTC
caché:      última fila OK del símbolo con created_at dentro de GEMINI_CACHE_SECONDS
breaker:    N=GEMINI_BREAKER_FAILURES fallos consecutivos ⇒ abierto
            GEMINI_BREAKER_SECONDS (estado en memoria del proceso)
```

## Respuesta de la API (serialización D-7)

```json
POST /api/bot/ai/analyze
{"symbol": "BTCUSDT", "force": false}
→ {"state": "OK", "cached": false,
   "recommendation": {"decision": "WAIT", "confidence": 0.64, "...": "..."},
   "evaluation": {"id": 1, "created_at": "...", "model": "...",
                  "prompt_version": "...", "coste_usd": "0",
                  "latency_ms": 812, "request_id": "..."}}
recommendation/evaluation a null cuando state != OK (salvo cache OK)
GET /api/bot/ai/recommendations?symbol=&limit=
→ {"recommendations": [{id, symbol, created_at, trigger, status,
                         decision, confidence (número), coste_usd (texto),
                         model, prompt_version, latency_ms}]}
```

## RF → test (mapeo obligatorio)

| RF | Fichero de test | Clase/prueba |
|---|---|---|
| RF-1 | `tests/test_ai_advisor_service.py` | `ContextBuildingTests` (contexto con 006 + cartera + límites, insumo ausente → marcado, sin inventar) |
| RF-2 | `tests/test_ai_schema.py` | `SchemaTests` (válido, campos de más, rangos, `SHORT`/`HOLD` inválidos, no-JSON) |
| RF-3 | `tests/test_ai_advisor_service.py` + `tests/test_gemini_client.py` | `QuotaBudgetTests` (cuota, presupuesto 0 USD, coste por tokens) · `GeminiQuotaTests` (429 sin reintento) |
| RF-4 | `tests/test_gemini_client.py` + `tests/test_ai_advisor_service.py` | `ClientResilienceTests` (timeout+retry, 5xx, cabecera con clave) · `BreakerCacheTests` (breaker, caché, `force`) |
| RF-5 | `tests/test_ai_isolation.py` | `IsolationTests` (bot_loop no importa IA; ninguna ruta de órdenes referencia evaluaciones) |
| RF-6 | `tests/test_ai_advisor_service.py` + `tests/test_ai_api.py` | `PersistenceTests` (fila completa, evento `ai.consultation`, fuente `gemini` en `source_health`) |
| RF-7 | `tests/test_ai_api.py` | `EndpointTests` (200 por estado, 404 universo, listado, sin token, sin 500) |
| RF-8 | `tests/test_ai_daily.py` | `DailyPassTests` (pasa 24 h, tops, corta en no-OK, no-op con auto off) |
| RF-9 | suite completa | tests de 001-006 sin tocar aserciones |

## Orden de implementación (rojo → verde)

T1 tests rojos (6 ficheros) → T2 config → T3 `ai_schema` →
T4 `gemini_client` → T5 `models` + `ai_advisor_service` →
T6 API + pasada diaria + router + eventos → T7 docs + validación final.

## Riesgos y mitigaciones

- **RF-9 / D-1**: cero edición de `bot_loop`/`decision_store`/órdenes; test
  de aislamiento en T1; si un test existente falla, se corrige la
  instrumentación nueva, nunca la aserción.
- **Coste real (D-2)**: presupuesto 0 USD + cuota diaria + 429 sin
  reintento; la clave no habilita pago por sí sola (corte en Google es
  externo: documentar en README que el proyecto usa solo free tier).
- **Clave filtrada**: cabecera `x-goog-api-key` (nunca URL), `redact` de
  005 en eventos y test RNF-3.
- **Modelo no verificado** (sin acceso a la doc oficial el 2026-10-07):
  `GEMINI_MODEL` configurable; el usuario confirma el modelo con free tier
  al crear la clave (brief §19).
- **Rate limit público Gemini**: cuota local + caché + pasada diaria única;
  sin sleeps largos en la suite (reintentos sin backoff, deterministas).
