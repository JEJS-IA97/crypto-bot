# crypto-bot — backend

Bot de trading de cripto en Binance Spot con capital mínimo (20 USD), construido
con metodología SDD. Las especificaciones viven en `../specs/`: `001-bot-binance-spot/`
(completa) y `002-nube-informe-diario/` (ejecución gratis en la nube + informe diario);
las reglas del proyecto en `../AGENTS.md` y `../docs/constitution.md`.

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
| Descargar velas (RF-15) | `.\.venv\Scripts\python.exe collect_klines.py --symbol BTCUSDT --interval 1h` |
| Backtest + grid sobre velas | `.\.venv\Scripts\python.exe train_strategy.py --klines-dir klines --plan ..\specs\001-bot-binance-spot\plan.md` |
| Testnet (manual, T20) | `.\.venv\Scripts\python.exe check_binance_testnet.py` |
| Informe diario manual | `.\.venv\Scripts\python.exe send_daily_report.py [--date YYYY-MM-DD]` |

## Estructura

- `app/api/` — FastAPI: routers (`/api/bot`, `/api/signals…`, `/simulation`, `/health`)
  y token de control `app/api/auth.py` (RF-20).
- `app/domain/` — reglas puras: `signal_engine.py` (señal EMA/RSI/volumen, RF-7),
  `risk_math.py` (tamaño de posición y límites, RF-4/RF-5/RF-12).
- `app/models.py`, `app/schemas.py`, `app/database.py`, `app/config.py`
  (ajustes `.env`; `Decimal` para todo valor monetario).
- `app/services/` — casos de uso: `bot_loop.py`, `risk_guard_service.py`,
  `decision_store.py`, `order_lifecycle.py`, `phase_service.py`,
  `binance_market_data_client.py`, `binance_executor.py`,
  `external_signal_service.py`, `strategy_lab_service.py`…
- `tests/` — un test por servicio/requisito (unittest + TDD; RF sin test = no implementado).

## Panel y API (resumen)

- `GET /api/bot/status` · `GET /api/bot/metrics` · `POST /api/bot/start` · `POST /api/bot/stop`
- `GET|POST /api/bot/phase` (SIMULATION → TESTNET → LIVE)
- `POST /api/signals/external` (señal externa con TTL, RF-8) · `GET /api/signals/decisions` (auditoría con snapshot, RF-10)
- `POST /api/webhooks/signal` (webhook)

## Fases y seguridad

- Órdenes reales solo con `ALLOW_LIVE_TRADING=true` **y** `CONFIGURED_CAPITAL_USD>0`
  **y** fase `LIVE` (RF-1/RF-2); fuera de simulación se exige `API_TOKEN` (RF-20).
- Límites fijados por spec: ≤1 USD por operación, ~5 USDT mínimo, pérdida diaria
  ≥5 % bloquea el día, ≤10 aperturas/día, 3 posiciones máx., breaker tras 5 fallos,
  stop 2 % / take-profit 4 %, TTL de señal 300 s.

## Zona congelada (RF-21)

No refactorizar ni ampliar: `arbitrage_service`, `trade_opportunity_service`,
`execution_price_service`, `bot_engine`, `bot_runner_service`,
`exchange_market_service`, `okx_demo_client`, `market_sync_service`
(+ sus dependencias `inventory_service`, `market_data_service`, sus tests y los CLIs
`check_okx_demo.py` y `collect_market_snapshots.py`). El baseline SHA-256 está en
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
