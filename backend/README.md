# crypto-bot — backend

Bot de trading de cripto en Binance Spot con capital mínimo (20 USD), construido
con metodología SDD. La especificación activa vive en `../specs/001-bot-binance-spot/`
(`spec.md`, `plan.md`, `tasks.md`); las reglas del proyecto en `../AGENTS.md` y
`../docs/constitution.md`.

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
