# Plan — Spec 006 (Data & context)

Ver `spec.md`. TDD estricto, `Decimal` en dominio, código en inglés,
español en docs/mensajes. Ningún módulo importa el loop de la 001.

## Módulos

| # | Módulo | Qué | RF |
|---|---|---|---|
| M1 | `app/config.py` | `fear_greed_url` (defecto API pública Alternative.me), `news_rss_feeds` (CSV, vacío), `depth_cache_seconds=30`, `fear_greed_cache_seconds=21600`, `news_cache_seconds=900`, `candidate_weights` (CSV `momentum:0.30,volume:0.25,trend:0.25,range:0.20`, claves en inglés como `DEFAULT_WEIGHTS`) | RF-3, RF-4, RF-6 |
| M2 | `app/services/binance_market_data_client.py` | `get_depth(symbol, limit=5)` y `get_ticker_24h(symbol)` reutilizando `_get` (timeout/moneda ya resueltos); payload parseado a `Decimal` | RF-2, RF-8 |
| M3 | `app/domain/feature_engine.py` | `FeatureVector` frozen (6 campos `Decimal \| None`) + `compute_features(candles, *, now, periods) -> FeatureVector`: retorno, volatilidad, posición en rango, z-score de volumen, dispersión EMA y RSI. Reutiliza `_ema`/`_rsi` de `signal_engine` (sin duplicar). Solo velas `open_time <= now` (RNF-3) | RF-5 |
| M4 | `app/domain/candidate_engine.py` | `DEFAULT_WEIGHTS`, `normalize_weights(csv)` (fallback a defecto, D-7), `score_candidate(features, weights) -> CandidateScore` con factores `{name, weight, normalized 0..1, contribution}` y `missing` si hay `null` obligatorio; puro y sin I/O | RF-6 |
| M5 | `app/services/market_context_service.py` | Caché TTL en memoria (`threading.Lock`), fetchers (`depth`, `ticker24`, `fng`, `rss`) con timeout ≤5 s, `mark_source` en éxito/fallo, `ContextSnapshot` frozen con estado por fuente (`HEALTHY/STALE/ERROR/DISABLED`) y flag `stale` (D-4/D-5); RSS 2.0 con `xml.etree` + dedup por hash de enlace | RF-1…RF-4, RF-8 |
| M6 | `app/services/candidate_service.py` | Orquesta: klines del cliente existente → features → score → ranking; marca `binance_klines` (RF-8); decide `missing_data` | RF-5, RF-6 |
| M7 | `app/api/routes/candidates.py` + `main.py` | `GET /api/bot/context/{symbol}` (404 si fuera de universo), `GET /api/bot/candidates?symbols=&limit=` (clamp 1…50); router registrado | RF-7 |
| M8 | eventos 005 | `context.fetched` (nivel INFO/WARNING) y `config.ignored` cuando los pesos son inválidos | RF-1, RF-6 |

## Modelos de dominio (dataclass frozen, sin tablas nuevas — D-4)

```text
FeatureVector: return_pct, volatility_pct, range_position_pct,
               volume_zscore, ema_spread_pct, rsi  (Decimal | None)
FactorContribution: name, weight, normalized, contribution (Decimal)
CandidateScore: symbol, score (Decimal 0-100), factors[], missing[]
ContextSource: state (HEALTHY/STALE/ERROR/DISABLED), fetched_at, stale (bool)
ContextSnapshot: symbol, fetched_at, order_book{spread_bps, imbalance,
                 bids[], asks[]}, ticker{last_price, change_pct_24h,
                 quote_volume_24h}, fear_greed{value, label},
                 news[{title,url,published_at}], sources{name: ContextSource}
```

## Pesos y normalización por defecto (RF-6)

| Factor | Peso | Entrada | Normalización (clamp) |
|---|---|---|---|
| momentum | 0.30 | retorno de 3 velas 15m | -2%..+2% → 0..1 |
| volume | 0.25 | z-score del último volumen (n=20) | -2..2 → 0..1 |
| trend | 0.25 | dispersión EMA(9/21) | -1%..+1% → 0..1 |
| range | 0.20 | posición en el rango del período | 0..1 directo |

`score = 100 · Σ (peso_i · normalizado_i)`; cualquier `null` → candidato
excluido con `filters=["missing_data"]` (D-6).

## RF → test (mapeo obligatorio)

| RF | Fichero de test | Clase/prueba |
|---|---|---|
| RF-1 | `tests/test_market_context.py` | `ContextSnapshotTests` (composición + estados por fuente) |
| RF-2 | `tests/test_market_context.py` | `OrderBookTests` (spread/imbalance/niveles + depth vacía + caché 30 s) |
| RF-3 | `tests/test_market_context.py` | `FearGreedTests` (ok, respuesta rara, URL vacía → DISABLED) |
| RF-4 | `tests/test_market_context.py` | `NewsFeedTests` (RSS ok, ítem malformado, sin feeds → DISABLED) |
| RF-5 | `tests/test_feature_engine.py` | `FeatureTests` (valores Decimal, insuficiencia → null, sin look-ahead) |
| RF-6 | `tests/test_candidate_engine.py` | `ScoringTests` (contribuciones suman, pesos custom, missing_data, orden) |
| RF-7 | `tests/test_candidates_api.py` | `ContextEndpointTests` + `CandidatesEndpointTests` (200/404/clamps) |
| RF-8 | `tests/test_market_context.py` | `SourceHealthIntegrationTests` (HEALTHY/ERROR vía `mark_source`) |
| RF-9 | suite completa | 279 tests de 001-005 sin tocar aserciones |

## Orden de implementación (rojo → verde)

T1 tests rojos → T2 config → T3 `feature_engine` → T4 `candidate_engine` →
T5 `market_context_service` (+ `get_depth`/`get_ticker_24h`) →
T6 `candidate_service` + API + router → T7 docs + validación final.

## Riesgos y mitigación

- **RF-9**: cero edición de `bot_loop`/`decision_store`/órdenes; si un test
  existente falla, se corrige la instrumentación nueva, nunca la aserción.
- **Rate limit público**: caché TTL + timeout 5 s + una sola llamada por
  TTL por fuente y símbolo.
- **Respuestas externas cambiantes**: todo parser es fail-soft (bloque no
  disponible + fuente ERROR, nunca 500).
- **Determinismo (RNF-3)**: features puras sobre velas; tests con fijas.
