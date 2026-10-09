# crypto-bot — backend

Bot de trading de cripto en Binance Spot con capital mínimo (20 USD), construido
con metodología SDD. Las especificaciones viven en `../specs/`: `001-bot-binance-spot/`
(completa, v3 con estrategia ORB), `002-nube-informe-diario/` (ejecución gratis en la
nube + informe diario), `003-panel-ui/` y `004-informe-html/`; las reglas del proyecto
en `../AGENTS.md` y `../docs/constitution.md`.

## Requisitos

- Python 3.14 con entorno virtual en `.venv/`.
- La suite de tests **no necesita red ni credenciales** (mockea `httpx`; RNF-2).

## Instalación

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cp .env.example .env   # valores por defecto seguros (live deshabilitado)
```

## Comandos (desde `backend/`)

| Acción | Comando |
| --- | --- |
| API en desarrollo | `.\.venv\Scripts\uvicorn.exe app.main:app --reload` |
| Tests (TDD, siempre en verde) | `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` |
| Lint | `.\.venv\Scripts\python.exe -m ruff check .` |
| Byte-compile | `.\.venv\Scripts\python.exe -m compileall app tests` |
| Descargar velas 15m (RF-15) | `.\.venv\Scripts\python.exe collect_klines.py --symbol BTCUSDT --interval 15m` |
| Descargar velas 5m para ORB (RF-15) | `.\.venv\Scripts\python.exe collect_klines.py --symbols BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT --interval 5m --data-dir data\klines5m` |
| Backtest ORB + comparativa con EMA/RSI | `.\.venv\Scripts\python.exe train_strategy.py --strategy both --klines-dir data\klines --klines-orb-dir data\klines5m --no-write-plan` |
| Testnet (manual, T20) | `.\.venv\Scripts\python.exe check_binance_testnet.py` |
| Informe diario manual | `.\.venv\Scripts\python.exe send_daily_report.py [--date YYYY-MM-DD]` |

## Estructura

- `app/api/` — FastAPI: routers (`/api/bot`, `/api/signals…`, `/simulation`, `/health`)
  y token de control `app/api/auth.py` (RF-20).
- `app/domain/` — reglas puras: `orb_engine.py` (señal **ORB** determinista
  `BUY`/`HOLD`, RF-7), `signal_engine.py` (EMA/RSI/volumen, solo candidata del
  backtest/grid, RF-15), `risk_math.py` (tamaño de posición y límites, RF-4/RF-5/RF-12).
- `app/models.py`, `app/schemas.py`, `app/database.py`, `app/config.py`
  (ajustes `.env`; `Decimal` para todo valor monetario).
- `app/services/` — casos de uso: `bot_loop.py`, `risk_guard_service.py`,
  `decision_store.py`, `order_lifecycle.py`, `phase_service.py`,
  `binance_market_data_client.py`, `binance_executor.py`,
  `external_signal_service.py`, `strategy_lab_service.py`…
- `tests/` — un test por servicio/requisito (unittest + TDD; RF sin test = no implementado).

## Estrategia ORB (spec 001 v3, RF-7)

- Rango de apertura con las **6 velas 5m de 9:00–9:30 AM de Nueva York**
  (`America/New_York`, DST incluido) de BTC, ETH, BNB y SOL (D-12).
- Entre las **9:30 y las 10:00 AM NY**: si el cierre supera el máximo del rango
  → `BUY` (una sola señal técnica por par por día NY, RF-27); rompimiento
  bajista o sin rompimiento → `HOLD` (Binance Spot sin cortos, D-13).
- Salidas por stop-loss/take-profit **RR 1:1** (`STOP_LOSS_PCT` =
  `TAKE_PROFIT_PCT` = 2.0, D-11) y señales externas en los 8 pares (RF-8).
- XRP, DOGE, ADA y LINK: solo señales externas (D-12). EMA/RSI queda como
  candidata del backtest/grid (RF-15), sin emisión en el loop.

## Panel y API (resumen)

- `GET /api/bot/status` · `GET /api/bot/metrics` · `POST /api/bot/start` · `POST /api/bot/stop`
- `GET|POST /api/bot/phase` (SIMULATION → TESTNET → LIVE)
- `POST /api/signals/external` (señal externa con TTL, RF-8) · `GET /api/signals/decisions` (auditoría con snapshot, RF-10)
- `POST /api/webhooks/signal` (webhook)
- `GET /api/bot/context/{symbol}` · `GET /api/bot/candidates` (solo lectura, spec 006 RF-7)

## Observabilidad (spec 005)

- Log JSON por línea con campos obligatorios: `timestamp` (UTC), `level`,
  `service`, `event`, `mode`, `result`, `correlation_id`, `asset`,
  `latency_ms`, `strategy_version`. Los secretos salen como `[REDACTED]`
  (RF-1/RF-4) y un fallo de log/persistencia nunca corta el ciclo (fail-open).
- Un `correlation_id` (UUID) por ciclo une los eventos con el snapshot de
  cada decisión emitida (RF-2).
- Eventos persistidos en `system_events`; salud de fuentes en `source_health`
  (`HEALTHY|DEGRADED|STALE|ERROR|DISABLED`, RF-5).
- Endpoints de solo lectura (sin token):
  - `GET /api/bot/events` — filtros `level`/`asset`/`correlation_id`,
    `limit` acotado a 1…200 (RF-6).
  - `GET /api/bot/sources` — estado de las fuentes (RF-5).
  - `GET /api/bot/observability` — agregados de las últimas 24 h (RF-7).
- Retención: `EVENT_RETENTION_DAYS` (defecto 30), purga al arrancar y como
  máximo cada 24 h (RF-8).
- Vars nuevas: `EVENT_RETENTION_DAYS`, `LOG_LEVEL`, `STRATEGY_VERSION`.

## Datos y contexto (spec 006)

- Fuentes declaradas (D-2): Binance Spot público (`depth` de los 5 mejores
  niveles y `ticker/24hr`, misma base que los klines), Alternative.me
  Fear&Greed y RSS configurable. Fuera de alcance: datos de futuros,
  CoinGecko/DefiLlama y cualquier servicio no declarado.
- Caché en memoria con TTL (D-4): depth 30 s, F&G 6 h, noticias 15 min.
  Fetch caído con caché → dato servido con `stale: true` (fuente `STALE`
  en el snapshot y `ERROR` en `source_health`); sin caché → bloque `null`
  y fuente `ERROR`. Nunca HTTP 500 por una fuente caída (D-5).
- Endpoints de solo lectura (sin token):
  - `GET /api/bot/context/{symbol}` — order book (`spread_bps`,
    `imbalance`, 5 mejores niveles), ticker 24 h, Fear&Greed y noticias,
    con `fetched_at` y estado por fuente; 404 `symbol_not_in_universe`
    fuera de `TRADING_SYMBOLS` (D-3).
  - `GET /api/bot/candidates?symbols=&limit=` — ranking 0-100 con score
    numérico y `factors` explicados (momentum 0.30 / volume 0.25 /
    trend 0.25 / range 0.20), `rank` y `excluded` con `filters`
    (`missing_data` / `data_unavailable`); `limit` acotado a 1…50.
- Features deterministas en `Decimal`, sin look-ahead ni ML: `null` cuando
  faltan velas y candidato excluido si falta una feature obligatoria
  (RF-5/RF-6; el LLM llega en la spec 007).
- Eventos 005: `context.fetched` (INFO si todo sano, WARNING si hay
  fuente `ERROR`/`STALE`) y `config.ignored` si `CANDIDATE_WEIGHTS` es
  inválido (se usan los pesos por defecto).
- Vars nuevas: `FEAR_GREED_URL`, `NEWS_RSS_FEEDS`, `DEPTH_CACHE_SECONDS`,
  `FEAR_GREED_CACHE_SECONDS`, `NEWS_CACHE_SECONDS`, `CANDIDATE_WEIGHTS`.

## Analista IA (spec 007)

- **Solo tier gratuito de Gemini (D-2)**: presupuesto duro `0` USD, cuota
  diaria `GEMINI_DAILY_QUERY_LIMIT` (defecto 4) y 429 de Google ⇒ fallo
  sin reintento. `GEMINI_API_KEY` vacía ⇒ estado `DISABLED` sin llamadas.
  `GEMINI_MODEL` (defecto `gemini-2.5-flash`) se confirma con la
  documentación oficial al crear la clave; nunca se habilita pago.
- Estados: `OK | DISABLED | QUOTA_EXCEEDED | BUDGET_EXCEEDED |
  BREAKER_OPEN | INVALID_RESPONSE | ERROR`. Cortes antes de consultar:
  presupuesto, cuota del día UTC y breaker (3 fallos ⇒ abierto 900 s,
  se cierra solo o con éxito). Caché de dictámenes `OK` 3600 s
  (`force: true` la salta).
- Contexto honesto (RF-1): snapshot 006 + features/score 006 + posiciones
  abiertas (`PositionV2`) + `DailyRiskState` + límites; lo que falta se
  marca en `data_quality`, nunca se inventa. I/O estricto (brief §6):
  `decision ∈ BUY|SELL|WAIT`, `direction ∈ LONG|NEUTRAL` (spot sin
  cortos); esquema Pydantic `extra="forbid"` con `SchemaViolation`.
- Endpoints sin token (RF-7; 404 `symbol_not_in_universe`, nunca 500):
  - `POST /api/bot/ai/analyze` `{symbol, force?}` → `{state, cached,
    recommendation, evaluation}` (`coste_usd` como texto, `confidence`
    como número, D-7).
  - `GET /api/bot/ai/recommendations?symbol=&limit=` — últimos
    dictámenes, `limit` acotado a 1…50 (defecto 20).
- Pasada diaria opcional (RF-8): `GEMINI_AUTO_ANALYSIS=true` + clave ⇒
  bucle horario que analiza el top-N de candidatos (`trigger: auto`) con
  guard de 24 h y parada en el primer estado no `OK` (evento WARNING).
  El loop de la 001 no importa IA (RF-5, `tests/test_ai_isolation.py`).
- Persistencia y observabilidad (RF-6): tabla `ai_evaluations` (coste en
  `Decimal`, tokens, latencia, `request_id`, contexto y respuesta), evento
  `ai.consultation` (INFO ok / WARNING degradado / ERROR fallo) y fuente
  `gemini` en `source_health` (módulo `gemini_client` sin SDK: REST con
  `x-goog-api-key`, nunca en URL ni en mensajes de error).
- Vars nuevas: `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL`,
  `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_RETRIES`,
  `GEMINI_DAILY_QUERY_LIMIT`, `GEMINI_CACHE_SECONDS`,
  `GEMINI_BREAKER_FAILURES`, `GEMINI_BREAKER_SECONDS`,
  `GEMINI_AUTO_ANALYSIS`, `GEMINI_AUTO_ANALYSIS_LIMIT`,
  `GEMINI_DAILY_BUDGET_USD`, `GEMINI_PRICE_MTOK_INPUT`,
  `GEMINI_PRICE_MTOK_OUTPUT`.

## Risk engine v2 (spec 008)

- **Envuelve `risk_guard.can_open` (D-1)**: `evaluate_open` delega las 4
  razones de la 001 (`daily_loss_limit`, `daily_open_limit`, `cooldown`,
  `position_error`) y añade `max_open_positions` (≤3),
  `max_exposure` (tope total) y `correlated_exposure` (resize). El loop
  evalúa **antes** de ordenar: `BLOCKED` ⇒ decisión `REJECTED` sin orden;
  `RESIZED` ⇒ la orden sale con `allowed_quantity`.
- **Exposición total (RF-4)**: `committed + requested ≤
  RISK_MAX_TOTAL_EXPOSURE_PCT %` (75 por defecto) × `CONFIGURED_CAPITAL_USD`;
  `committed = Σ quantity × average_entry_price` de las posiciones `OPEN`.
- **Correlación y resize (D-2/D-3)**: Pearson sobre los últimos 60 cierres
  15m ya descargados (≥30 retornos, varianza > 0; sin datos ⇒ `unknown` y no
  actúa). Si `r ≥ RISK_CORRELATION_THRESHOLD` (0.7) ⇒ resize a
  `min(pedido, 12.5 % × capital)` flooreado al `step_size`; si ese tamaño
  queda por debajo de `min_notional` ⇒ se permite el original con
  `resize_applied=false`.
- **Auditoría (RF-7)**: cada evaluación emite el evento `risk.evaluated`
  (servicio `risk_engine`; INFO en `allow`, WARNING en `resized`/`blocked`)
  con motivo, importes, correlaciones, `resize_applied` y límites.
- **Endpoint sin token (RF-6)**: `GET /api/bot/risk/exposure` → capital,
  comprometido, disponible (`SimulationBalance` de
  `SIMULATION_BOT_ACCOUNT_ID`), tope, % de uso, `headroom_usd`, posiciones,
  por activo, por dirección (LONG/NEUTRAL) y límites; decimales como texto;
  cuenta ausente ⇒ `available_usd: null` con 200 (nunca 500).
- **Tabla 1 (reglas de test: precio ≈100, `min_notional` 5, stop 2 %)**:

  | Capital | Pedido | Si correlacionada (r ≥ 0.7) |
  |---|---|---|
  | 10 USD | 5 | resize no ejecutable; 2ª apertura denegada por tope |
  | 20 USD | 5 | resize no ejecutable ⇒ original (`resize_applied=false`) |
  | 50 USD | 12.5 | RESIZED → 6.2 (qty 0.062) |
  | 100 USD | 25 | RESIZED → 12.5 (qty 0.125) |
  | 1000 USD | 50 | sin cambio (pedido ya ≤ mitad del share) |

- Vars nuevas: `RISK_MAX_TOTAL_EXPOSURE_PCT`, `RISK_CORRELATION_THRESHOLD`.
  Tests: `test_risk_engine`, `test_risk_capitals`, `test_risk_api`,
  `test_portfolio_math` (+ defaults en `test_config`).

## Consola de control (spec 009)

- **4 endpoints nuevos (solo lectura)**: `GET /api/bot/ai/stats` (agregados
  de `ai_evaluations` 24 h), `GET /api/bot/pipeline` (catálogo fijo de 22
  nodos con estado derivado de `source_health` y eventos 005),
  `GET /api/bot/decisions/{id}/why` y `GET /api/bot/decisions/{id}/replay`
  (reconstrucción determinista sobre snapshot + eventos + IA + posición;
  secciones sin dato en `unavailable` con motivo; 404 si la decisión no
  existe).
- **Enlace equity→decisión (D-10)**: `simulation_trades.decision_id`
  (nullable, indexada) poblada en la entrada (`protection_after_fill`) y la
  salida (`close_position`) del bot vía `link_fill_to_decision`
  (`raw.simulation_trade_id`); expuesta en `TradeResponse` y
  `TradeHistoryResponse`. Trades manuales quedan sin enlace.
- Sin tablas nuevas de datos; sin SSE/WebSocket; sin dependencias nuevas.
  Tests: `test_ai_stats_api`, `test_pipeline_api`, `test_why_api`,
  `test_replay_api`, `test_trade_decision_link`.

## Fases y seguridad

- Órdenes reales solo con `ALLOW_LIVE_TRADING=true` **y** `CONFIGURED_CAPITAL_USD>0`
  **y** fase `LIVE` (RF-1/RF-2); fuera de simulación se exige `API_TOKEN` (RF-20).
- Límites fijados por spec: ≤1 USD por operación, ~5 USDT mínimo, pérdida diaria
  ≥5 % bloquea el día, ≤10 aperturas/día, 3 posiciones máx., breaker tras 5 fallos,
  stop 2 % / take-profit 2 % (RR 1:1, D-11), TTL de señal 300 s.

## Zona congelada (RF-21)

No refactorizar ni ampliar: `arbitrage_service`, `trade_opportunity_service`,
`execution_price_service`, `bot_engine`, `bot_runner_service`,
`exchange_market_service`, `okx_demo_client`, `market_sync_service`
(+ sus dependencias `inventory_service`, `market_data_service`, `risk_service`,
sus tests y los CLIs `check_okx_demo.py` y `collect_market_snapshots.py`). El baseline
SHA-256 está en
`../specs/001-bot-binance-spot/frozen_zone.json` y lo verifica
`tests/test_frozen_zone.py`, que además ejecuta la sub-suite congelada.

## Nube gratis (spec 002)

El bot corre 24/7 sin coste (detalle en `../specs/002-nube-informe-diario/`):

| Pieza | Dónde | Por qué |
| --- | --- | --- |
| API + bucle del bot | **Render free** (`render.yaml`) | auto-arranque + keepalive cada 9 min (RF-1) |
| Base de datos | **Neon free** (Postgres) | SQLite no sobrevive a los reinicios de Render free (RF-2) |
| Informe diario 08:00 UTC | **GitHub Actions → Gmail SMTP** | Render free bloquea el SMTP saliente desde 2025-09-26 (RF-3) |
| Panel | **GitHub Pages** | estático y gratis; habla con Render vía CORS + token (RF-8) |

### Puesta en marcha (5 pasos)

1. **Neon (Postgres gratis):** crea un proyecto y copia el *pooled connection string*.
2. **Render:** *New + Blueprint* con este repo (usa `render.yaml`, plan free, root
   `backend`). Env vars del blueprint:
   - `DATABASE_URL` = URL de Neon,
   - `API_TOKEN` = token fuerte (p. ej. `openssl rand -hex 32`),
   - `KEEPALIVE_URL` = URL pública del servicio (`https://<nombre>.onrender.com`),
   - `CORS_ORIGINS` = origen de Pages, **sin ruta**: `https://<usuario>.github.io`
     (el navegador nunca envía la ruta en `Origin`; se confirma en el paso 4).
   `SIMULATION_BOT_ENABLED=true` ya viene en el blueprint.
3. **Gmail:** activa la verificación en 2 pasos y genera una **contraseña de
 aplicación** (Google → Contraseñas de apps). Secrets de GitHub: `SMTP_USER`
   (tu Gmail), `SMTP_PASS` (la contraseña de aplicación), `REPORT_TO` (destinatario
   del informe). Nunca van en el código ni en `.env` del repo (RF-4).
4. **GitHub Pages:** repo **público** → *Settings → Pages → Source: GitHub Actions*;
   crea la variable de repo `VITE_API_URL` con la URL de Render y, con el **origen**
   de Pages (`https://jejs-ia97.github.io`, sin `/crypto-bot`), actualiza
   `CORS_ORIGINS` en Render (los valores con ruta se normalizan solos).
5. **Primer correo y kill switch:** *Actions → Informe diario → Run workflow* (o
   espera al cron de las 08:00 UTC); abre el panel, pega el `API_TOKEN` en
   «Token de control» y usa Detener/Arrancar (RF-6). En local:
   `python send_daily_report.py` con tu `.env`.

Notas: el límite gratis de Render son 750 h/mes (un servicio siempre despierto usa
~744 h); si Render suspende el servicio, el informe diario **sigue saliendo** desde
Actions, que lee Neon directamente (RF-5). En local todo sigue en SQLite (`.env`),
sin tocar la nube (RNF-5).

## Testnet

1. Genera las claves en **https://testnet.binance.vision/** (login con tu cuenta de
   **GitHub**, botón *Generate HMAC_SHA256 key*) y ponlas en `.env`:
   `BINANCE_API_KEY` / `BINANCE_API_SECRET`. Ese `.env` está en `.gitignore`.
2. Comprueba la conexión (manual, **no forma parte de la suite diaria**, RNF-2):

   ```powershell
   .\.venv\Scripts\python.exe check_binance_testnet.py
   ```

   Salida esperada: `Account type: SPOT`, `Permissions: ['SPOT']`, balances de
   prueba, `BTCUSDT status: TRADING` y `Binance Spot Testnet connection OK.`
   (verificado el 2026-10-05).
3. Paso a fase `TESTNET`: `POST /api/bot/phase` con `{"phase": "TESTNET"}`.
   El backend lo rechaza hasta cumplir **RF-16 / D-9**: ≥30 días en SIMULATION,
   ≥15 operaciones, PnL neto >0 tras comisiones, drawdown ≤10 % y backtest con
   signo positivo en validación **y** test (la evidencia del backtest viaja en el
   payload del cambio de fase). El detalle de lo que falta se devuelve en la
   respuesta. Pasar de TESTNET a LIVE exige además testnet rentable (RF-16).
