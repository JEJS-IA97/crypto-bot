# Tasks — Spec 007

Ver `spec.md` y `plan.md`. Metodología: TDD (rojo → verde), suite completa
en verde, marcar checkbox y reportar antes de pasar a la siguiente tarea.

- [x] **T1 — Tests rojos.** `tests/test_ai_schema.py`,
  `tests/test_gemini_client.py`, `tests/test_ai_advisor_service.py`,
  `tests/test_ai_api.py`, `tests/test_ai_daily.py` y
  `tests/test_ai_isolation.py` con los casos del mapeo RF→test (fallan por
  ImportError mientras no existan los módulos).

- [x] **T2 — Config.** Las 14 vars `GEMINI_*` de M1 en `config.py` +
  defaults testeados en `test_config.py` (clave vacía y presupuesto 0 por
  defecto).

- [x] **T3 — `ai_schema`.** `AdvisorResponse` estricto + `from_json` con
  `SchemaViolation` (RF-2).

- [x] **T4 — `gemini_client`.** REST con `httpx`, cabecera con la clave,
  `GeminiReply`, reintentos solo ante timeout/5xx, 429 ⇒
  `GeminiQuotaExceeded` sin reintento (RF-3/RF-4 parcial).

- [ ] **T5 — `models` + `ai_advisor_service`.** Tabla `ai_evaluations`,
  estados DISABLED/cuota/presupuesto/breaker/caché, construcción de
  contexto (006 + cartera + riesgo), coste por tokens, evento
  `ai.consultation`, fuente `gemini` en `KNOWN_SOURCES` (RF-1, RF-3,
  RF-4, RF-6).

- [ ] **T6 — API + pasada diaria.** Endpoints `POST /api/bot/ai/analyze` y
  `GET /api/bot/ai/recommendations` (404 universo, sin token, sin 500,
  RF-7), `ai_daily_analysis` con guard de 24 h (RF-8), router en `main.py`
  + lifespan condicional. **RF-5/RF-9: test de aislamiento + suite 001-006
  intacta.**

- [ ] **T7 — Documentación y validación final.** `.env.example` y
  `backend/README.md` (vars Gemini, estados, endpoints, "solo free tier
  0 USD", confirmar modelo con la doc oficial); `ruff check .` limpio;
  `python -m compileall -q app`; suite backend completa en verde; marcar RF
  como implementados en `spec.md` y reportar.
