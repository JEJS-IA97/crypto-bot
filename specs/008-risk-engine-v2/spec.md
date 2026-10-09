# Spec 008 — Risk engine v2 (veto y redimensión)

Estado: implementada (T1-T7 completadas; aprobada por el propietario el
2026-10-07). Relación: deriva de 001 (RF-4/RF-5/RF-12/RF-22/RF-26 que
**envuelve sin sustituir**), 005 (eventos + retención), 006 (velas 15m del
ciclo como insumo de correlación) y complementa 007 (la recomendación de la
IA pasa por este motor antes de cualquier tamaño; el LLM nunca toca órdenes).
Fuente: brief §7 (pipeline `DATA → … → RISK ENGINE → EXECUTION` y respuestas
`ORDER RESIZED/BLOCKED`), §8 (cálculos del motor de riesgo y ejemplos de
veto/redimensión), `docs/fase0-diagnostico-brief-ia.md` §6 (gap), §7 (línea
175: "[008] risk_engine v2: envuelve al risk_guard actual"), §8 (roadmap),
§17 (property tests) y §19 (criterios 008), constitución #3/#7/#8/#10/#11;
decisiones del propietario del 2026-10-07 (D-1, D-3 y D-9).

## Contexto

La 001 puso los límites duros (pérdida diaria ≤5%, ≤10 aperturas/día,
cooldown, ≤1 USD por operación, sizing 25%, ≤3 posiciones) repartidos entre
`risk_guard_service` y `risk_math`, pero hoy el bucle solo consulta
`risk_guard.can_open` + `calculate_order_size`: **no existe** un componente
que calcule la exposición comprometida, que evalúe correlación entre
posiciones ni que pueda decir "la orden es BLOCKED/RESIZED" con motivo y
límites (diagnóstico §6). El brief exige ese motor como paso independiente
obligatorio entre la señal y la ejecución (§7/§8), auditable para la UI
(§19: "respuestas BLOCKED/RESIZED auditables; UI las muestra" → 009).

## Decisiones de diseño

- **D-1 · El engine envuelve el loop** (decisión del propietario): `_try_open`
  de `bot_loop` sustituye la llamada directa a `risk_guard.can_open` por
  `risk_engine_service.evaluate_open`, que la ejecuta como **primera**
  comprobación. Las razones de la 001 (`daily_loss_limit`,
  `daily_open_limit`, `cooldown`, `position_error`) se conservan literalmente
  y la suite 001-007 sigue verde sin tocar aserciones (RF-2).
- **D-2 · Correlación positiva con velas ya cargadas**: coeficiente de Pearson
  sobre rendimientos percentuales de los últimos 60 cierres 15m (los que el
  ciclo ya descargó; **sin llamadas nuevas de red**) entre la candidata y cada
  otra posición abierta. `r ≥ RISK_CORRELATION_THRESHOLD` (defecto 0.7) con
  ≥30 rendimientos y varianza > 0 ⇒ correlacionada; sin datos, ventana corta
  o varianza 0 ⇒ `unknown` y **no actúa**. Solo correlación positiva (cartera
  long-only, D-13 de la 001).
- **D-3 · Resize a la mitad del share con suelo de mínimo** (propietario:
  policy (a)): si correlacionada, `allowed = min(requested, capital aportado ×
  12.5%)` (la mitad del share 25% de RF-12), flooreado al `step_size`. Si
  `allowed < min_notional` del exchange el resize **no es ejecutable** ⇒ se
  permite el tamaño original y el evento anota `resize_applied=false`. La
  matriz de D-9 mide el efecto en5 capitales; ajustar la política durante la
  implementación no reescribe esta spec.
- **D-4 · Auditoría por eventos 005** (propietario): `evaluate_open` emite
  `risk.evaluated` en **cada** evaluación (INFO `allow`, WARNING `resized` /
  `blocked`) con requested/allowed/motivo/límites/correlación y el
  `correlation_id` del ciclo. Sin tabla nueva (retención de 30 días de la
  005, constitución #10). `decision.blocked` de la 001/005 sigue apareciendo
  vía `mark_rejected`: los dos eventos son complementarios (decisión + motor).
- **D-5 · RF-12 enchufado por fin**: `can_open_position` (≤3 posiciones) hoy
  solo se usa en informes y tests, no en el bucle (gap declarado en
  diagnóstico §6). El motor lo evalúa con motivo `max_open_positions`.
- **D-6 · Exposición total sobre el capital aportado**: `committed + requested
  ≤ RISK_MAX_TOTAL_EXPOSURE_PCT%` (defecto **75** = 3 × 25%) de
  `settings.configured_capital_usd`. Base fija = capital aportado
  (constitución #3: las ganancias no relajan ni disparan el límite); motivo
  `max_exposure`. Usar los mismos `settings` que el sizing de la 001 mantiene
  el comportamiento existente intacto.
- **D-7 · Por activo y por dirección se calculan, no vetan**: en el bucle la
  candidata nunca tiene posición abierta (se gestiona aparte), así que un
  veto por activo sería redundante hoy; el motor los expone en el snapshot y
  en el evento para la UI (brief §8) junto a `headroom_usd` (margen de
  exposición disponible = coste de oportunidad simple de diagnóstico §7).
- **D-8 · Motor sin IA y sin red**: `risk_engine_service` no importa ningún
  módulo de la 007 ni `httpx` (test de aislamiento) y solo lee BD + las
  velas del ciclo. Una posición abierta en un símbolo fuera de la lista del
  ciclo queda `unknown` en ese par (universo fijo; D-B3 pendiente).
- **D-9 · Matriz de capitales en la suite** (propietario): sesiones simuladas
  deterministas (velas fijas, sin red) en **10 / 20 / 50 / 100 / 1000 USD**
  que validan los invariantes por capital y dejan la Tabla 1 de
  comportamiento dentro de la suite.

## Requisitos funcionales

- **RF-1 — Evaluación previa obligatoria.** CUANDO el bucle vaya a abrir
  posición (señal técnica o externa), EL SISTEMA evalúa la apertura con
  `evaluate_open` **antes** de enviar la orden; CUANDO el resultado sea
  `BLOCKED`, NINGUNA orden se envía y la decisión queda `REJECTED` con el
  motivo visible; CUANDO sea `RESIZED`, la orden se envía con
  `allowed_quantity`.
- **RF-2 — Continuidad de la 001.** `evaluate_open` DELEGA en
  `risk_guard.can_open` como primera comprobación conservando sus cuatro
  razones (`daily_loss_limit`, `daily_open_limit`, `cooldown`,
  `position_error`); la suite completa de 001-007 sigue verde **sin** tocar
  aserciones existentes.
- **RF-3 — Máximo de posiciones.** CUANDO haya 3 posiciones abiertas en la
  cuenta, EL SISTEMA bloquea la siguiente apertura con
  `max_open_positions` (RF-12); con 2 o menos, no bloquea por este motivo.
- **RF-4 — Exposición total.** CUANDO `committed + requested` supere el tope
  (`RISK_MAX_TOTAL_EXPOSURE_PCT` % del capital aportado), EL SISTEMA bloquea
  con `max_exposure`; DEBE cumplirse el invariante: toda apertura no
  bloqueada respeta `committed + requested ≤ tope` y `allowed ≤ requested`.
- **RF-5 — Correlación con redimensión.** CUANDO la correlación positiva con
  otra posición abierta alcance el umbral, EL SISTEMA REDIMENSIONA la orden
  a `min(requested, 12.5 % × capital aportado)` flooreado al step, siempre
  que ese tamaño sea ≥ `min_notional`; CUANDO falten datos o la ventana sea
  insuficiente, DEBE anotar `unknown` y no actuar; CUANDO el resize no sea
  ejecutable por el mínimo del exchange, DEBE permitir el tamaño original y
  anotar `resize_applied=false`; CUANDO no haya correlación, DEBE permitir
  sin cambios.
- **RF-6 — Snapshot de exposición.** `GET /api/bot/risk/exposure` devuelve
  200 sin token con capital, comprometido, disponible, tope, porcentaje de
  uso, `headroom_usd`, posiciones abiertas, exposición **por activo** y **por
  dirección** (LONG/NEUTRAL) y los límites vigentes; decimales serializados
  como texto (convención 006/007); ninguna condición produce HTTP 500.
- **RF-7 — Auditoría de intervenciones.** CADA evaluación EMITE el evento
  `risk.evaluated` (servicio `risk_engine`) con `symbol, action, reason,
  requested_usd, allowed_usd, committed_usd, exposure_cap_usd,
  open_positions, correlations, max_correlation, resize_applied, limits` y el
  `correlation_id` del ciclo; las intervenciones BLOCKED/RESIZED quedan además
  reflejadas en `decision.blocked` (motivo de la decisión rechazada).
- **RF-8 — Matriz de capitales.** La suite EJECUTA sesiones deterministas en
  10/20/50/100/1000 USD que AFIRMAN por capital: pérdida estimada por
  operación ≤ 1 USD, ≤ 3 posiciones abiertas, exposición total ≤ tope, ≤ 10
  aperturas/día, pérdida diaria ≤ 5 % y la conducta de resize de la Tabla 1.
- **RF-9 — Aislamiento.** NINGÚN módulo del motor importa el analista IA de
  la 007 (`ai_advisor_service`, `gemini_client`, `ai_schema`) ni `httpx`;
  la implementación NO añade llamadas de red al ciclo (las correlaciones se
  calculan sobre las velas ya descargadas).

Tabla 1 — Comportamiento esperado por capital (reglas de test: precio ≈ 100,
`step_size` 0.001, `min_notional` 5, stop 2 % ⇒ tope de riesgo 50 USD;
base de exposición = `configured_capital_usd`):

| Capital | Pedido (sizing) | Mitad del share (12.5 %) | Si correlacionada (r ≥ 0.7) |
|---|---|---|---|
| 10 USD | 5 (mínimo) | 1.25 | resize no ejecutable → tamaño original con `resize_applied=false`; segunda apertura denegada por saldo o tope |
| 20 USD | 5 (mínimo) | 2.5 | resize no ejecutable → tamaño original con `resize_applied=false` |
| 50 USD | 12.5 | 6.25 | **RESIZED** 12.5 → 6.2 (qty 0.062, floor al step) |
| 100 USD | 25 | 12.5 | **RESIZED** 25 → 12.5 (qty 0.125, floor al step) |
| 1000 USD | 50 (tope de riesgo) | 125 | sin cambio: el pedido ya está por debajo de la mitad del share |

## Requisitos no funcionales

- **RNF-1 — Sin red en la suite**: motor y matriz se prueban con las
  fakes/velas existentes; cero llamadas externas nuevas.
- **RNF-2 — `Decimal` en todo** (correlaciones, exposiciones, topes); los
  eventos y la API serializan decimales como texto; `float` prohibido.
- **RNF-3 — Sin tablas nuevas ni migraciones**: la persistencia es por
  eventos 005; `Base.metadata.create_all` sigue siendo el único mecanismo.
- **RNF-4 — Determinismo**: mismas velas y misma BD ⇒ misma evaluación
  (timestamps y correlation_id inyectables), property tests repetibles.

## Casos límite

1. `state.blocked` (pérdida diaria) ⇒ `BLOCKED daily_loss_limit` (razón de
   la 001 intacta, delegada).
2. Posición en estado `ERROR` ⇒ `BLOCKED position_error` (delegada).
3. `opens_count ≥ 10` ⇒ `BLOCKED daily_open_limit` (delegada); cooldown de
   300 s por símbolo ⇒ `BLOCKED cooldown`.
4. Tres posiciones abiertas ⇒ `BLOCKED max_open_positions` (nuevo: antes
   pasaba).
5. `committed + requested` un centímetro por encima del tope ⇒
   `BLOCKED max_exposure`; exactamente en el tope ⇒ permitido.
6. Correlación con varianza 0 (velas planas o idénticas) ⇒ `unknown`, sin
   acción.
7. Posición abierta en símbolo sin velas en el ciclo ⇒ ese par `unknown`;
   los demás pares se evalúan.
8. Capital 20 USD y r = 0.9 ⇒ resize a 2.5 < `min_notional` ⇒ tamaño
   original + `resize_applied=false` (D-3).
9. Capital 100 USD y r = 0.9 ⇒ `RESIZED` 25 → 12.5 con
   `allowed_quantity` flooreado al step (pérdida estimada ≤ 1 USD).
10. Dos evaluaciones en el mismo ciclo ⇒ dos eventos `risk.evaluated` con el
    mismo `correlation_id` (uno por evaluación, sin duplicados internos).

## Fuera de alcance

- UI de intervenciones "por qué se vetó/redimensionó" → spec 009 (aquí solo
  API de lectura + eventos).
- Correlaciones con series externas o precios fuera de las velas del ciclo
  (requiere red ⇒ spec nueva).
- Shorts, apalancamiento o exposición por dirección SHORT → D-B1 → spec 012.
- Cambiar los límites de la 001 (5 % diario, 10/día, cooldown, breaker,
  1 USD/operación): aquí **solo se consumen** (D-6 solo añade el tope de
  exposición total configurable).
- Reemplazar `risk_guard_service`/`risk_math` (frozen): se envuelven.
- Coste de oportunidad avanzado (rendimiento alternativo por capital),
  learning → specs 010+.
- Multi-cuenta de simulación para paper-trading paralelo por capital →
  spec propia.

## Requisitos → tests

| RF | Tests |
|---|---|
| RF-1 | `test_risk_engine.LoopIntegrationTests` (BLOCKED ⇒ REJECTED sin orden; RESIZED ⇒ orden con `allowed_quantity`) |
| RF-2 | `test_risk_engine.DelegationTests` (4 razones de la 001) + suite 001-007 completa intacta |
| RF-3 | `test_risk_engine.PositionLimitTests` |
| RF-4 | `test_risk_engine.ExposureTests` (invariantes `allowed ≤ requested` y `committed + requested ≤ tope`) |
| RF-5 | `test_risk_engine.CorrelationTests` (resize, sin datos, suelo de mínimo, sin correlación) |
| RF-6 | `test_risk_api.ExposureEndpointTests` (200, campos, texto decimal, sin token, sin 500) |
| RF-7 | `test_risk_engine.EventTests` (payload completo, un evento por evaluación) |
| RF-8 | `test_risk_capitals` (`SingleOpenSessionTests` + `CorrelatedSecondOpenTests`: Tabla 1 + invariantes por capital) |
| RF-9 | `test_risk_engine.IsolationTests` (sin imports de 007 ni `httpx` en el motor) |

## Criterios de finalización

1. ✅ RF-1…RF-9 con test rojo→verde y mapeados en `plan.md`.
2. ✅ Suite backend completa en verde (434 tests) + `ruff check` limpio.
3. ✅ `.env.example` y `backend/README.md` actualizados (vars de riesgo,
   endpoint y Tabla 1).
4. ✅ Aprobación explícita del propietario antes del paso a la siguiente spec
   (2026-10-07).
