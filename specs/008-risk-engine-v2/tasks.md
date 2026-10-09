# Tasks — Spec 008

Ver `spec.md` y `plan.md`. Metodología: TDD (rojo → verde), suite completa
en verde, marcar checkbox y reportar antes de pasar a la siguiente tarea.

- [x] **T1 — Tests rojos.** `tests/test_portfolio_math.py`,
  `tests/test_risk_engine.py`, `tests/test_risk_capitals.py` y
  `tests/test_risk_api.py` con los casos del mapeo RF→test (fallan por
  ImportError mientras no existan los módulos) + defaults
  `RISK_MAX_TOTAL_EXPOSURE_PCT=75` y `RISK_CORRELATION_THRESHOLD=0.7`
  testeados rojos en `test_config.py`.

- [x] **T2 — Config.** Las 2 vars de riesgo de M1 en `config.py` con sus
  defaults (Decimal) y tests en verde en `test_config.py`.

- [x] **T3 — `portfolio_math`.** `pct_returns`, `pearson` (None con pocos
  puntos o varianza 0, clamp [-1,1]), `correlate_closes` (ventana 60 /
  mín. 30 retornos), `halved_share` y `floor_to_step` puros y en verde
  (RF-5 base).

- [x] **T4 — `risk_engine_service`.** `RiskAction`, `RiskAssessment`
  congelado, `evaluate_open` con el orden de 5 pasos (delegación →
  posiciones → exposición → correlación → evento), `exposure_snapshot` y
  evento `risk.evaluated` (RF-2, RF-3, RF-4, RF-5, RF-7 a nivel unidad).

- [x] **T5 — Integración en `bot_loop`.** `_try_open` con
  `candles_by_symbol`, `evaluate_open` en el sitio de `can_open`,
  `BLOCKED` ⇒ `mark_rejected` sin orden, `RESIZED` ⇒
  `allowed_quantity` (RF-1); **RF-2: suite 001-007 intacta sin tocar
  aserciones** + `LoopIntegrationTests` e `IsolationTests` en verde.

- [x] **T6 — API de exposición + matriz.** `GET /api/bot/risk/exposure`
  sin token y sin 500 (RF-6) con router en `main.py`; matriz de capitales
  10/20/50/100/1000 con la Tabla 1 y los invariantes en verde (RF-8).

- [x] **T7 — Documentación y validación final.** `.env.example` y
  `backend/README.md` (vars de riesgo, endpoint, Tabla 1); `ruff check .`
  limpio; `python -m compileall -q app`; suite backend completa en verde;
  marcar RF como implementados en `spec.md` y reportar.
