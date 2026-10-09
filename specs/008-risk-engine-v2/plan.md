# Plan — Spec 008 (Risk engine v2, veto/redimensión)

Ver `spec.md`. TDD estricto, `Decimal` en dominio, código e identificadores
en inglés, docs/mensajes en español. El motor **envuelve** `risk_guard` y
`risk_math` sin sustituirlos (frozen) y no importa nada de la 007 (D-8/RF-9).

## Módulos

| # | Módulo | Qué | RF |
|---|---|---|---|
| M1 | `app/config.py` | `risk_max_total_exposure_pct: Decimal = 75`, `risk_correlation_threshold: Decimal = 0.7` | RF-4, RF-5 |
| M2 | `app/domain/portfolio_math.py` | Puro, sin red/BD: `pct_returns(closes)`, `pearson(xs, ys) -> Decimal | None` (None con <2 puntos o varianza 0; clamp a [-1, 1]), `correlate_closes(candidate, other, *, window=60, min_returns=30) -> Decimal | None`, `halved_share(capital_usd) -> Decimal` (= capital × `MAX_POSITION_SHARE` / 2), `floor_to_step(value, step)` | RF-5 |
| M3 | `app/services/risk_engine_service.py` | `RiskAction` (Enum: `allow|resized|blocked`), `RiskAssessment` (`dataclass(frozen=True)`), `evaluate_open(db, *, symbol, now, state, account_id, quantity, price, candles, other_candles, step_size, min_notional_usd, available_usd, correlation_id=None) -> RiskAssessment` y `exposure_snapshot(db, *, account_id, available_usd=None) -> dict` | RF-1…RF-5, RF-7 |
| M4 | `app/services/bot_loop.py` | `_try_open` recibe `candles_by_symbol` (2 call sites del ciclo) y sustituye `can_open(...)` por `evaluate_open(...)`; `BLOCKED` ⇒ `mark_rejected` + return sin orden; `RESIZED` ⇒ `quantity = allowed_quantity`; kill switch y emisión de `order.sent` intactos; import de `can_open` eliminado si queda sin uso | RF-1, RF-2 |
| M5 | eventos 005 | `risk.evaluated` (servicio `risk_engine`; INFO `allow` / WARNING `resized`/`blocked`) con payload de RF-7; valores `Decimal` como texto | RF-7 |
| M6 | `app/api/routes/risk.py` + `main.py` | `GET /api/bot/risk/exposure` (sin token, sin 500): snapshot M3 con cuenta `settings.simulation_bot_account_id` y disponible de `SimulationBalance` | RF-6 |
| M7 | `.env.example`, `backend/README.md` | Vars de riesgo, endpoint, Tabla 1 | RF-4…RF-6 |
| M8 | `tests/test_portfolio_math.py`, `tests/test_risk_engine.py`, `tests/test_risk_capitals.py`, `tests/test_risk_api.py` | Mapeo RF→test de `spec.md` (+ defaults de config en `test_config.py`) | RF-1…RF-9 |

## Modelos de dominio (`dataclass(frozen=True)` / `Enum`)

```text
RiskAction: allow | resized | blocked          (str Enum)

RiskAssessment:
  action: RiskAction
  reason: str                      # "" en allow; motivos 001 o nuevos (M3)
  symbol: str
  requested_usd: Decimal
  allowed_usd: Decimal             # 0 si blocked
  allowed_quantity: Decimal | None # cantidad a usar (None si blocked)
  committed_usd: Decimal
  available_usd: Decimal
  exposure_cap_usd: Decimal
  open_positions: int
  correlations: dict[str, str | None]   # por símbolo abierto: "0.83" | None
  max_correlation: Decimal | None
  resize_applied: bool

Motivos nuevos:  max_open_positions | max_exposure | correlated_exposure
Motivos delegados (001): daily_loss_limit | daily_open_limit | cooldown
                         | position_error
```

## Fórmulas e invariantes

```text
tope_exposicion = configured_capital_usd × RISK_MAX_TOTAL_EXPOSURE_PCT / 100
committed       = Σ quantity × average_entry_price   (PositionV2 OPEN, cuenta)
requested_usd   = quantity × price                    (post-sizing de la 001)

resize (D-3): allowed = min(requested_usd,
                           configured_capital_usd × MAX_POSITION_SHARE / 2)
              flooreado a step_size × price
              ejecutable ⟺ allowed ≥ min_notional_usd
              si no ejecutable → action=allow, resize_applied=false

correlación (D-2): retornos pct de los últimos 60 cierres (15m) de cada par
              r = Σ(x−x̄)(y−ȳ) / sqrt(Σ(x−x̄)² · Σ(y−ȳ)²)   (Decimal, clamp [-1,1])
              r ≥ RISK_CORRELATION_THRESHOLD con ≥30 retornos y varianza > 0
              sin datos/ventana/varianza → None ("unknown")

invariantes (RF-4/RF-8, property tests):
  action != blocked  ⟹  requested_usd ≤ allowed_usd ≤ requested_usd (allow)
  action == resized  ⟹  0 < allowed_usd < requested_usd ∧ allowed ≥ min_notional
  action != blocked  ⟹  committed + requested_usd ≤ tope_exposicion
  pérdida estimada del pedido ≤ 1 USD (la garantiza el sizing de la 001 y
  allowed ≤ requested la conserva en el resize)
```

## Orden de ejecución dentro de `evaluate_open`

```text
1. risk_guard.can_open          → blocked (razones 001)
2. open_positions ≥ 3           → blocked max_open_positions
3. committed + requested > tope → blocked max_exposure
4. correlación con otras abiertas (candles ya cargados)
     r ≥ umbral y resize ejecutable → resized correlated_exposure
     r ≥ umbral y no ejecutable     → allow + resize_applied=false
     unknown / sin correlación      → allow
5. emitir risk.evaluated (siempre) y devolver RiskAssessment
```

## Respuesta de la API (serialización: decimales como texto)

```json
GET /api/bot/risk/exposure
→ {"capital_usd": "20", "committed_usd": "5", "available_usd": "15",
   "exposure_cap_usd": "15", "exposure_pct": "25",
   "headroom_usd": "10", "open_positions": 1, "max_open_positions": 3,
   "by_asset": {"ETHUSDT": "5"},
   "by_direction": {"LONG": "5", "NEUTRAL": "0"},
   "limits": {"daily_loss_limit_pct": "5", "max_opens_per_day": 10,
              "max_loss_per_trade_usd": "1", "max_position_share": "0.25",
              "max_total_exposure_pct": "75", "correlation_threshold": "0.7",
              "cooldown_seconds": 300, "breakers_failures": 5}}
```

## RF → test (mapeo obligatorio)

| RF | Fichero de test | Clase/prueba |
|---|---|---|
| RF-1 | `tests/test_risk_engine.py` | `LoopIntegrationTests` (con fakes tipo `test_orb_loop`: BLOCKED ⇒ REJECTED sin evento `order.sent`; RESIZED ⇒ orden con `allowed_quantity`) |
| RF-2 | `tests/test_risk_engine.py` + suite completa | `DelegationTests` (las 4 razones de la 001 llegan sin cambiar) + 001-007 verdes sin tocar aserciones |
| RF-3 | `tests/test_risk_engine.py` | `PositionLimitTests` (2 abiertas pasa, 3 bloquea) |
| RF-4 | `tests/test_risk_engine.py` | `ExposureTests` (en el tope pasa, un centímetro más bloquea; invariantes `allowed ≤ requested`, `committed + requested ≤ tope`) |
| RF-5 | `tests/test_risk_engine.py` + `tests/test_portfolio_math.py` | `CorrelationTests` (resize, unknown, suelo `min_notional`, sin correlación) · `PearsonTests`/`CorrelateTests` (x vs x = 1, simetría, constante → None, ventana corta → None) |
| RF-6 | `tests/test_risk_api.py` | `ExposureEndpointTests` |
| RF-7 | `tests/test_risk_engine.py` | `EventTests` (payload completo, un evento por evaluación, correlation_id) |
| RF-8 | `tests/test_risk_capitals.py` | `SingleOpenSessionTests` + `CorrelatedSecondOpenTests` (subtests por capital sobre la Tabla 1 + invariantes) |
| RF-9 | `tests/test_risk_engine.py` | `IsolationTests` (imports del motor sin 007 ni `httpx`, estilo `test_ai_isolation`) |

## Sesiones de la matriz (RF-8, D-9)

Por cada capital C ∈ {10, 20, 50, 100, 1000} (patch de
`settings.configured_capital_usd` + cuenta de simulación con saldo C):

- **Sesión A (apertura única)**: ciclo ORB determinista con fakes
  existentes ⇒ la posición abierta respeta `notional ≤ tope(C)`,
  pérdida ≤ 1 USD, `committed ≤ tope(C)` y se emite `risk.evaluated`.
- **Sesión B (con correlación)**: se abre primero ETHUSDT y en el siguiente
  ciclo se evalúa BTCUSDT con velas correlacionadas (r ≥ 0.7) ⇒ resultado de
  la Tabla 1 por capital (allow original con `resize_applied=false` en
  10/20, RESIZED en 50/100, sin cambio en 1000) y, en 10 USD, la segunda
  apertura queda denegada (saldo/tope) sin orden.

## Orden de implementación (rojo → verde)

T1 tests rojos (4 ficheros + config) → T2 config → T3 `portfolio_math` →
T4 `risk_engine_service` + evento `risk.evaluated` → T5 integración en
`bot_loop` (RF-1/RF-2, suite 001-007 intacta) → T6 API de exposición +
matriz de capitales en verde → T7 docs + validación final.

## Riesgos y mitigaciones

- **RF-2 / D-1 (lo más delicado)**: tocar `_try_open` puede alterar la 001.
  Mitigación: delegación exacta de `can_open` en el primer paso; los vetos
  nuevos solo añaden razones `max_open_positions`/`max_exposure`/
  `correlated_exposure`; la base de exposición usa
  `settings.configured_capital_usd` (20 por defecto ⇒ tope 15 USD y resize
  inactivo con las reglas actuales), así que los escenarios de 001 (pedido ≈5
  USD, ≤2 posiciones por BD) no se rozan. Si un test existente cayese, se
  ajusta la instrumentación nueva, nunca la aserción.
- **Velas idénticas en fakes ⇒ r = 1**: el resize podría dispararse donde la
  001 no lo espera. Mitigación: suelo `min_notional` (D-3) + Tabla 1 fija el
  comportamiento esperado por capital; la matriz y `CorrelationTests` lo
  acotan.
- **Falso positivo de correlación** (series sintéticas o muy cortas):
  umbral configurable, ≥30 retornos y varianza > 0; `unknown` nunca bloquea
  (sin humo, constitución #9).
- **`Decimal.sqrt` y precisión**: clamp a [-1, 1] y property test
  `pearson(x, x) == 1`.
- **Doble evento**: `risk.evaluated` (motor) + `decision.blocked`
  (decisión) son complementarios; test garantiza un solo
  `risk.evaluated` por evaluación.
- **Coste por ciclo**: el motor solo consulta en los candidatos a apertura
  (≤ universo por ciclo; aperturas ≤10/día) y reutiliza las velas ya
  descargadas.
