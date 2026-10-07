# Spec 007 — Analista IA (Gemini, recomendación pura)

Estado: borrador en revisión (pendiente de aprobación del usuario).
Relación: complementa 001 (loop intacto, RF-9), 005 (eventos + `source_health`)
y 006 (contexto y candidatos como insumo). Fuente: brief §6, §7, §19, §24-§27
y §Fase 5; `docs/fase0-diagnostico-brief-ia.md` §7/§10/§11/§19; decisiones
del propietario del 2026-10-07 (D-B4 cerrada).

## Contexto

La spec 006 dejó contexto por símbolo (order book, ticker, Fear&Greed,
noticias) y candidatos con score explicado. El brief exige un analista IA que
consuma ese contexto **estructurado y compacto** y produzca recomendaciones
auditables (§6), estrictamente separado de la ejecución (§7): el risk engine
con veto/redimensión llega en la 008 y el loop ORB de la 001 no se toca.
Esta spec cablea Gemini por REST con `httpx` (sin SDK) bajo presupuesto duro
de **0 USD** — solo tier gratuito.

## Decisiones de diseño

- **D-1 · Recomendación pura** (brief §7, constitución #9): ninguna orden ni
  decisión del loop nace del LLM. La recomendación se persiste y se expone
  por API de solo lectura; `bot_loop` no importa nada de esta spec (RF-5
  lo verifica con test).
- **D-2 · Presupuesto duro 0 USD** (D-B4 del propietario): solo tier
  gratuito de Gemini. `GEMINI_DAILY_BUDGET_USD=0` con precios por defecto 0
  ⇒ cualquier coste estimado > 0 corta la consulta (`BUDGET_EXCEEDED`); si
  Google devuelve 429 (cuota agotada) → fallo honesto sin reintento. El
  coste por consulta se **registra** siempre: `coste_usd = (tokens entrada ·
  precio entrada + tokens salida · precio salida) / 1e6`, con
  `GEMINI_PRICE_MTOK_*` configurables (defecto 0) para trazabilidad si
  algún día se habilita pago (requiere spec nueva).
- **D-3 · Disparo doble** (decisión del propietario): (a) endpoint bajo
  demanda para panel/curl y (b) pasada diaria automática **opcional**
  (`GEMINI_AUTO_ANALYSIS`, defecto `false`) sobre los N candidatos top.
  El loop de la 001 sigue intacto (RF-9).
- **D-4 · I/O estricto** (brief §6): contexto JSON compacto (los datos de
  006 + cartera y presupuesto de riesgo de 001); respuesta validada con
  esquema Pydantic `extra="forbid"`. Campos del brief: `decision`,
  `direction`, `confidence`, `setup_quality`, `risk_flags`,
  `supporting_factors`, `contradicting_factors`, `invalidating_conditions`,
  `time_horizon`, zonas sugeridas, `reason_codes`, `required_next_check`,
  `data_quality`. `decision ∈ {BUY, SELL, WAIT}` y `direction ∈ {LONG,
  NEUTRAL}` (Binance Spot sin cortos, D-13). Prompt y esquema en inglés
  (identificadores en inglés), mensajes de UI en español. Sin cadena de
  pensamiento privada: se muestra el resumen estructurado, no "reasoning".
- **D-5 · Resiliencia** (brief §19): timeout ≤10 s, reintentos ≤2 (nunca
  sobre 429), cuota diaria (defecto 4), circuit breaker en memoria
  (3 fallos ⇒ abierto 15 min), caché por símbolo (1 h), `request_id`,
  `model` y `prompt_version` en cada evaluación.
- **D-6 · Secretos** (brief §19/§26): `GEMINI_API_KEY` solo en backend
  (`.env`/secretos de Render), nunca en frontend, logs ni eventos (el
  `redact` de 005 ya protege claves; la clave viaja por cabecera
  `x-goog-api-key`, jamás en la URL).
- **D-7 · Decimal** en costes y en `confidence`/`setup_quality` del dominio;
  la API serializa `coste_usd` como texto y `confidence` como número
  (convención de la 006).

## Requisitos funcionales

- **RF-1 — Consulta estructurada.** CUANDO se pida analizar un símbolo del
  universo (D-3), EL SISTEMA construye un contexto JSON compacto con los
  datos de la 006 (contexto + features + score del símbolo), la cartera
  abierta (`PositionV2`) y el presupuesto de riesgo de 001
  (`DailyRiskState`, límites), y lo envía a Gemini dentro de su cuota;
  CUANDO falte un insumo, EL SISTEMA lo marca como no disponible en el
  contexto en vez de inventarlo.
- **RF-2 — Respuesta validada.** EL SISTEMA valida la respuesta del modelo
  contra un esquema estricto (campos, tipos, rangos `0..1`,
  `extra="forbid"`); CUANDO la respuesta no cumpla el esquema, EL SISTEMA
  la registra como `INVALID_RESPONSE` con la culpa visible y **no** deriva
  ningún campo por su cuenta.
- **RF-3 — Cuota, presupuesto y coste.** EL SISTEMA corta la consulta cuando
  la cuota diaria (`GEMINI_DAILY_QUERY_LIMIT`, defecto 4) se agota
  (`QUOTA_EXCEEDED`) o cuando el coste estimado supera el presupuesto
  (`GEMINI_DAILY_BUDGET_USD=0`, `BUDGET_EXCEEDED`), y REGISTRA por
  evaluación tokens, `coste_usd` y latencia; 429 de Google ⇒ fallo sin
  reintento.
- **RF-4 — Resiliencia.** EL SISTEMA aplica timeout, reintentos ≤2 (5xx/timeouts
  únicamente), circuit breaker (3 fallos consecutivos ⇒ abierto
  `GEMINI_BREAKER_SECONDS`, `BREAKER_OPEN` sin llamar) y caché de
  evaluaciones por símbolo (`GEMINI_CACHE_SECONDS`, `force` la salta);
  cada mecanismo es testeable por separado.
- **RF-5 — Recomendación pura.** NINGÚN módulo de ejecución importa el
  analista: `bot_loop` no menciona IA (test de aislamiento) y ninguna
  transición de fase/orden depende de una evaluación guardada.
- **RF-6 — Persistencia auditable.** CADA consulta (manual o diaria) GUARDA
  una fila en `ai_evaluations` con `symbol`, `trigger`, `created_at`,
  `request_id`, `correlation_id`, `model`, `prompt_version`, latencia,
  tokens, `coste_usd`, el contexto enviado y la respuesta validada (o el
  error); EL SISTEMA emite el evento 005 `ai.consultation` y marca la
  fuente `gemini` en `source_health` en éxito/fallo.
- **RF-7 — API de lectura.** `POST /api/bot/ai/analyze` {symbol, force} y
  `GET /api/bot/ai/recommendations?symbol=&limit=` DEVUELVEN 200 con
  `state` (`OK|DISABLED|QUOTA_EXCEEDED|BUDGET_EXCEEDED|BREAKER_OPEN|
  INVALID_RESPONSE|ERROR`), `cached` y la recomendación o `null`, SIN token
  (solo lectura, criterio RF-20 de la 001); 404 `symbol_not_in_universe`
  fuera de `TRADING_SYMBOLS` (D-3); ninguna condición de esta spec produce
  HTTP 500.
- **RF-8 — Análisis diario programado.** CUANDO `GEMINI_AUTO_ANALYSIS=true`
  y hay clave, EL SISTEMA ejecuta como máximo una pasada cada 24 h sobre
  los `GEMINI_AUTO_ANALYSIS_LIMIT` candidatos top (defecto 3) respetando
  cuota/presupuesto/breaker, y PARA con evento WARNING en cuanto una
  consulta no devuelve `OK`; desactivado por defecto y sin tocar el loop.
- **RF-9 — Cero cambio de comportamiento.** NI el loop de la 001 NI órdenes
  ni decisiones cambian: la suite completa de 001-006 sigue verde sin
  modificar aserciones existentes.

## Requisitos no funcionales

- **RNF-1 — Sin dependencias nuevas**: REST de Gemini con `httpx` (ya
  presente) y Pydantic v2 (ya presente); sin SDK `google-genai`.
- **RNF-2 — Suite sin red**: cliente, servicio y API se prueban con `httpx`
  mockeado / cliente falso; ninguna llamada real en la suite. Smoke real
  manual opcional (CLI tipo `check_binance_testnet.py`, fuera de la suite).
- **RNF-3 — Sin secretos**: la clave no aparece en URLs, logs, eventos ni
  respuestas de la API (auditable con test).
- **RNF-4 — Determinismo auditable**: misma respuesta mockeada y mismos
  datos ⇒ misma evaluación persistida (timestamps e `request_id`
  inyectables).

## Casos límite

1. Sin `GEMINI_API_KEY` o `GEMINI_MODEL` vacío → `state=DISABLED`,
   recomendación `null`, sin llamada ni fila (patrón 006).
2. Cuota diaria agotada → `QUOTA_EXCEEDED`, sin llamada a Gemini.
3. Coste estimado > presupuesto (0 por defecto) → `BUDGET_EXCEEDED`.
4. Breaker abierto → `BREAKER_OPEN`, sin llamada; se cierra solo a los
   `GEMINI_BREAKER_SECONDS` o con éxito.
5. JSON no parseable o fuera de esquema (campo de más, `confidence>1`,
   `direction: SHORT`, `decision: HOLD`) → `INVALID_RESPONSE` + fila con
   error.
6. Timeout/5xx → reintentos ≤2 y después `ERROR` + fuente `gemini` en
   `ERROR`; 429 → `QUOTA_EXCEEDED` sin reintento.
7. Caché fresca para el símbolo → respuesta servida con `cached=true` sin
   consumir cuota; `force=true` la salta.
8. Símbolo fuera del universo → 404 `symbol_not_in_universe`.
9. Pasada diaria con claves insuficientes de cuota → analiza lo que pueda y
   termina con WARNING (no reintenta dentro del día).

## Fuera de alcance

- Risk engine con veto/redimensión (`ORDER RESIZED/BLOCKED`) → spec 008.
- UI del panel "Why?"/control room → spec 009.
- Grounding con Google Search (brief §24, evaluar después, no dependencia).
- Learning/hipótesis, fine-tuning, registro de `prompt_versions` como tabla
  → specs 010+ (aquí solo constante `prompt_version` por evaluación).
- Pago a Google (tier gratuito únicamente, D-2) y shorts (D-B1 → 012).
- Reutilización del LLM dentro del loop de decisiones → prohibida (D-1).

## Criterios de finalización

1. RF-1…RF-9 con test rojo→verde y mapeados en `plan.md`.
2. Suite backend completa en verde + `ruff check` limpio.
3. `.env.example` y `backend/README.md` actualizados (vars de Gemini).
4. Aprobación explícita del usuario antes del paso a la siguiente spec.
