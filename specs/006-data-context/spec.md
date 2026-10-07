# Spec 006 — Data & context: adaptadores, features y candidatos

Estado: **implementada** (T1-T7 completadas; 318 tests verdes en la suite
backend; aprobación de usuario registrada por tarea).
Relación: complementa 001 (loop ORB intacto) y 005 (usa `source_health` y
`emit`). Fuente: brief §5, §18-§24, §Fase 2-3 y `docs/fase0-diagnostico-
brief-ia.md` §15/§16.

## Contexto

Hoy solo hay OHLCV + exchangeInfo + ticker de Binance. El brief exige contexto
multidimensional y un filtro/candidatos con scores explicados **antes** de que
cualquier IA recomiende nada. Esta spec construye la capa de datos y features
deterministas, sin LLM (llega en la 007) y sin tocar el trading.

## Decisiones de diseño

- **D-1 · Asesor puro**: el loop de la 001 no cambia; contexto y candidatos
  se exponen por API de solo lectura (mismo criterio que RF-9 de la 005).
- **D-2 · Fuentes declaradas** (constitución, servicios externos): Binance
  Spot público (depth/ticker, misma base y claves que RF-6 de la 001),
  Alternative.me Fear&Greed (API abierta, sin clave) y RSS configurable.
  **Fuera**: CoinGecko/DefiLlama, datos de futuros (funding/OI → decisión
  D-B2), opciones on-chain y cualquier otro servicio no declarado aquí.
- **D-3 · Universo fijo**: los 8 pares de `TRADING_SYMBOLS` (4 ORB) hasta
  que D-B3 apruebe expansión; el endpoint admite `?symbols=` acotado a ese
  universo.
- **D-4 · Caché en memoria con TTL** (sin tablas nuevas en 006): depth 30 s,
  F&G 6 h, noticias 15 min. Si el fetch falla y hay caché, se sirve marcado
  `stale: true`; si no hay caché, el dato sale "no disponible".
- **D-5 · Degradación honesta** (brief §5 "no inventar datos"): fuente caída
  → `mark_source(..., ok=False)` + campo `null` + `sources` con estado
  `ERROR/STALE`; ninguna feature se fabrica.
- **D-6 · Score explicado, sin ML**: 4 factores con pesos explícitos y
  contribución por factor en la respuesta; factores no disponibles → el
  candidato se excluye con `filters: ["missing_data"]` (fail-closed).
- **D-7 · `Decimal`** para todo valor numérico de features/precios en el
  dominio; en la API se serializan como texto (convención del repo). El
  score (0-100) tampoco es dinero, pero se mantiene `Decimal` y sale como
  número.

## Requisitos funcionales

- **RF-1 — Contexto por símbolo.** CADA solicitud de contexto de un símbolo
  DEL SISTEMA combina order book (spread, imbalancia, mejores niveles),
  ticker 24 h y Fear&Greed, CON `fetched_at` por fuente y estado por fuente;
  CUANDO una fuente falle, EL SISTEMA la marca en `source_health` y devuelve
  ese bloque como no disponible sin inventar valores.

- **RF-2 — Order book.** EL SISTEMA obtiene `GET /api/v3/depth` y calcula
  `spread_bps`, `imbalance` (bid/ask de los 5 mejores niveles, -1..1) y las
  mejores 5 entradas de bid/ask, CON caché de 30 s. Una profundidad vacía o
  no parseable ES no disponible (nunca lanza 500).

- **RF-3 — Fear&Greed.** MIENTRAS `FEAR_GREED_URL` no esté vacío, EL
  SISTEMA consulta Alternative.me y expone `value` (0-100) y `label` con
  caché de 6 h; URL vacía → fuente `DISABLED` y bloque no disponible. Una
  respuesta inesperada ES no disponible + fuente `ERROR`.

- **RF-4 — Noticias RSS.** MIENTRAS `NEWS_RSS_FEEDS` (CSV) no esté vacío,
  EL SISTEMA parsea RSS 2.0 (stdlib), deduplica por hash de enlace y devuelve
  hasta 10 titulares con `title/url/published_at` y caché de 15 min; sin
  feeds → fuente `DISABLED` y lista vacía; un ítem malformado SE omite.

- **RF-5 — Features deterministas.** PARA CADA símbolo, EL SISTEMA calcula
  sobre las velas ya descargadas (15m/5m del cliente existente): retorno de
  N velas, volatilidad de N velas, posición en el rango, z-score de volumen,
  dispersión EMA corta/larga y RSI, EN `Decimal` y SIN look-ahead (solo
  velas con `open_time` ≤ `now`); CADA feature es `null` si sus entradas no
  alcanzan (insuficiencia de velas) en vez de estimarse.

- **RF-6 — Candidatos con score explicado.** EL SISTEMA puntúa cada símbolo
  del universo de 0-100 con 4 factores (momentum 0.30, volume 0.25, trend
  0.25, range 0.20 — claves en inglés, pesos por defecto sobreescribibles con
  `CANDIDATE_WEIGHTS`), DEVUELVE la normalización y contribución de cada
  factor, el rango, y la lista de filtros aplicados; CUANDO falte una feature
  obligatoria, EL SISTEMA excluye al candidato con `filters=["missing_data"]`.
  El orden es score descendente.

- **RF-7 — API de lectura.** `GET /api/bot/context/{symbol}` y
  `GET /api/bot/candidates` (opcional `?symbols=`, `?limit=` ≤ 50) DEVUELVEN
  200 con los datos por fuente y sus timestamps, SIN token (solo lectura,
  RF-20 de la 001), 404 si el símbolo no pertenece al universo (D-3).

- **RF-8 — Salud y rate limit.** CADA fuente consultada (depth, ticker,
  fear_greed, news, klines) SE marca en `source_health` en éxito/fallo
  (reutiliza spec 005); los fetches usan timeout ≤ 5 s y la caché TTL para
  no agotar el rate limit público.

- **RF-9 — Cero cambio de comportamiento.** NI el loop de la 001 NI las
  órdenes NI las decisiones cambian: la suite completa sigue verde sin
  modificar aserciones existentes.

## Requisitos no funcionales

- **RNF-1 — Sin dependencias nuevas** (stdlib: `xml.etree`, `hashlib`;
  `httpx` ya presente para lo que no cubre el cliente).
- **RNF-2 — Suite sin red**: todos los fetches se prueban con `httpx`
  mockeado / cliente falso (patrón de `test_binance_market_data.py`).
- **RNF-3 — Sin look-ahead ni humo**: features y scores deterministas y
  reproducibles a partir de las mismas velas (brief §36).
- **RNF-4 — Sin secretos** en respuestas ni eventos (usa `emit` de 005).

## Casos límite

1. Depth vacía o `bids/asks` ausentes → bloque order book no disponible, fuente `ERROR`.
2. Caída de red con caché → datos servidos con `stale: true` y fuente `STALE` en el snapshot (la fila de `source_health` queda en `ERROR`, RF-8).
3. Caída de red sin caché → bloque `null`, fuente `ERROR`, HTTP 200 (nunca 500).
4. Menos velas que el periodo de la feature → feature `null`; si es obligatoria → candidato excluido.
5. `NEWS_RSS_FEEDS` vacío o feed caído → lista vacía + `DISABLED`/`ERROR`, sin error.
6. RSS con fecha inválida → ítem omitido; resto de ítems intactos.
7. `CANDIDATE_WEIGHTS` mal formado o suma ≠ 1 → se usan los pesos por defecto y se loguea warning (evento `config.ignored` vía 005).
8. `?symbols=` con símbolo ajeno al universo → 404 con motivo (D-3).
9. `limit` fuera de rango → clamp a [1, 50].

## Fuera de alcance

- LLM/Gemini, coste IA → spec 007.
- Universo dinámico (D-B3), datos de futuros/derivados (D-B2), shorts (D-B1) → specs condicionales.
- Persistencia de snapshots/features para replay → spec 009 (replay) decidirá el modelo.
- Sentimiento de noticias como factor de score (se muestran, no puntúan).
- Cualquier influencia en decisiones u órdenes del loop (RF-9).

## Criterios de finalización

1. RF-1…RF-9 con test rojo→verde y mapeados en `plan.md`.
2. Suite backend completa en verde + `ruff check` limpio.
3. `.env.example` y `backend/README.md` actualizados (vars de contexto).
4. Aprobación explícita del usuario antes del paso a la siguiente spec.

## RF → test (verificación final, T7)

| RF | Fichero de test | Estado |
|---|---|---|
| RF-1 | `tests/test_market_context.py` (`ContextSnapshotTests`) + `tests/test_candidates_api.py` (`ContextEndpointTests`) | implementado |
| RF-2 | `tests/test_market_context.py` (`OrderBookTests`) + `tests/test_binance_market_data.py` (`DepthAndTickerTests`) | implementado |
| RF-3 | `tests/test_market_context.py` (`FearGreedTests`) | implementado |
| RF-4 | `tests/test_market_context.py` (`NewsFeedTests`) | implementado |
| RF-5 | `tests/test_feature_engine.py` (`FeatureTests`) | implementado |
| RF-6 | `tests/test_candidate_engine.py` (`ScoringTests`) + `tests/test_candidates_api.py` (`EventTests.test_config_ignored…`) | implementado |
| RF-7 | `tests/test_candidates_api.py` (`ContextEndpointTests` + `CandidatesEndpointTests`) | implementado |
| RF-8 | `tests/test_market_context.py` (`SourceHealthIntegrationTests`) + `tests/test_binance_market_data.py` | implementado |
| RF-9 | suite completa 001-005 sin tocar aserciones (318 tests OK) | implementado |

RNF-1 (stdlib, sin dependencias nuevas), RNF-2 (suite sin red),
RNF-3 (sin look-ahead ni humo) y RNF-4 (sin secretos) verificados en T7
con `ruff check .`, `python -m compileall -q app` y la suite completa.
