# Tasks — Spec 006

Ver `spec.md` y `plan.md`. Metodología: TDD (rojo → verde), suite completa
en verde, marcar checkbox y reportar antes de pasar a la siguiente tarea.

- [x] **T1 — Tests rojos.** `tests/test_feature_engine.py`,
  `tests/test_candidate_engine.py`, `tests/test_market_context.py` y
  `tests/test_candidates_api.py` con los casos del mapeo RF→test (fallan
  por ImportError mientras no existan los módulos).

- [x] **T2 — Config.** `fear_greed_url`, `news_rss_feeds`,
  `depth_cache_seconds`, `fear_greed_cache_seconds`, `news_cache_seconds`,
  `candidate_weights` en `config.py` + defaults testeados en `test_config.py`.

- [x] **T3 — `feature_engine`.** `FeatureVector` y las 6 features en
  `Decimal` con corte por `now` (sin look-ahead) y `null` ante datos
  insuficientes (RF-5).

- [x] **T4 — `candidate_engine`.** Pesos por defecto + `normalize_weights`
  con fallback, normalizaciones clamp, contribuciones y `missing_data`
  (RF-6).

- [x] **T5 — `market_context_service` + cliente.** `get_depth` y
  `get_ticker_24h` en `BinanceMarketDataClient`; caché TTL con lock;
  fetchers de depth/ticker/F&G/RSS con `mark_source` y degradación
  `stale/no disponible` (RF-1…RF-4, RF-8).

- [x] **T6 — Servicio de candidatos + API.** `candidate_service`
  (klines → features → score → ranking), endpoints
  `GET /api/bot/context/{symbol}` y `GET /api/bot/candidates` (404 por
  universo, clamps 1…50), router en `main.py` (RF-7) y eventos 005
  (`context.fetched`, `config.ignored`). **RF-9: suite 001-005 intacta.**

- [x] **T7 — Documentación y validación final.** `.env.example` y
  `backend/README.md` (vars de contexto, endpoints nuevos, fuentes
  declaradas D-2); `ruff check .` limpio; `python -m compileall -q app`;
  suite backend completa en verde; marcar RF como implementados en
  `spec.md` y reportar.
