# Plan — Spec 002 (Fase 4, v2)

Derivado de `spec.md` v2. Stack: Python 3.14 (FastAPI en Render free, stdlib para correo,
`httpx` para keepalive) + PostgreSQL (Neon) + GitHub Actions (solo informe y Pages).
Zona congelada de la spec 001: **intacta** (RF-21 vigente).

## Arquitectura

```
Render (web service free, 24/7)                     GitHub (gratis)
┌──────────────────────────────────────┐            ┌────────────────────────────────────┐
│ uvicorn app.main:app                 │            │ Actions daily-report.yml           │
│  lifespan:                          │            │  cron 0 8 * * * (+dispatch)        │
│   ├─ create_all (SQLite|Postgres)    │  ←Neon ←  │  pip install → send_daily_report.py│
│   ├─ bot_loop.run (SIMULATION_BOT_   │  (solo     │   → build_daily_report()           │
│   │   ENABLED=true)          [RF-1a] │   lectura) │   → send_email() Gmail SMTP 587    │
│   └─ keepalive self-ping 9 min[RF-1b]│            │   [RF-3, RF-4, RF-5]               │
│ database_url = DATABASE_URL (Neon)   │            │ Actions pages.yml                  │
│ CORS_ORIGINS + API_TOKEN    [RF-6,8] │  ←HTTPS←   │  npm ci/test/build → deploy Pages  │
└──────────────────────────────────────┘   panel     └────────────────────────────────────┘
        ↑ Bearer <API_TOKEN>                         render.yaml (blueprint)
   Panel GitHub Pages (estático, VITE_API_URL)
```

- El informe **lee** Neon desde Actions (no escribe) → RF-5 garantizado aunque el bot esté
  detenido o Render suspenda el servicio (el correo sigue saliendo).
- `keepalive` es un self-ping a la URL pública (pasa por el LB de Render → cuenta como
  tráfico inbound) sin dependencias externas.
- El auto-arranque ya existe en `main.py` (H3): no se toca `bot_loop` (congelado).

## Hitos (M) → tareas (T) → tests

| M | Fichero | Tests | RF |
|---|---|---|---|
| M1 | `app/services/report_service.py` | `tests/test_report_service.py` (RED escrito ✓) | RF-3, RF-5 |
| M2 | `app/config.py` (SMTP_*, REPORT_TO) + `app/services/email_service.py` | `tests/test_email_service.py`, `tests/test_config.py` (ampliar) | RF-4, RF-7 |
| M3 | `send_daily_report.py` (CLI) | `tests/test_send_daily_report.py` | RF-3, RF-4, RF-5 |
| M4 | `app/database.py` (guards PG) + `requirements.txt` (`psycopg[binary]`) | `tests/test_database_postgres.py` (compilación de esquemas PG) | RF-2 |
| M5 | `app/services/keepalive_service.py` + `main.py` (tarea en lifespan) | `tests/test_keepalive_service.py` | RF-1 |
| M6 | `app/config.py`/`main.py` (`CORS_ORIGINS`) + frontend (`VITE_API_URL`, campo token) | `tests/test_cors.py` + `frontend/src/api/*.test.js` | RF-6, RF-8 |
| M7 | `render.yaml`, `.github/workflows/daily-report.yml`, `.github/workflows/pages.yml` | `tests/test_workflows.py` (texto) | RF-1, RF-3, RF-4, RF-8 |
| M8 | README (setup Neon/Render/Pages/Secrets/Gmail) + recorrida RF | — | todos |

## Contratos

### `report_service.build_daily_report(db, *, account_id=None, now=None) -> str`
Texto plano UTF-8 en español, líneas exactas (cada sección siempre presente;
«sin datos» si la BD no tiene `SimulationBalance`/métricas):
```
Informe diario — crypto-bot — YYYY-MM-DD (UTC)
Fase: <SIMULATION|...>
Estado: <activo|detenido|bloqueado (motivo)>
Balance: disponible X | posiciones Y | total Z            (Decimal, 8 decimales; money())
PnL: realizado X | no realizado Y | drawdown Z%           | PnL: sin datos (…)
Día UTC: pérdida X (bloqueado: sí/no) | aperturas n/10 | posiciones abiertas n/3 | «Día UTC: sin datos (…)»
Últimas 24 h: n decisiones — ejecutadas e, rechazadas r, pendientes p, con error err — motivos: motivo (n) | «Últimas 24 h: sin datos (0 decisiones)»
Breaker: <activo (motivo)|inactivo>
```
Sin `float` (constitución #11); fechas UTC naive (`utc_now()`).

### `email_service.send_email(*, subject, body, to, host, port, user, password) -> None`
`smtplib.SMTP(host, port, timeout=10)` → `starttls()` → `login()` → `send_message()`
(`EmailMessage`, texto plano). Errores → excepción con mensaje claro **sin** la contraseña.

### `send_daily_report.py [--date YYYY-MM-DD]`
Crea esquema si falta → `build_daily_report` → `send_email`. Sin `REPORT_TO`/`SMTP_PASS` →
`SystemExit` con mensaje claro (fail-closed). Lee `DATABASE_URL` del entorno (Actions inyecta
el de Neon; local usa `.env`/SQLite). `--date` para reenvíos manuales.

### `keepalive_service`
- `should_keepalive(url) -> bool`: false si url vacía (local) o sin `http(s)://`.
- `run_ping(url, *, client) -> bool`: GET con timeout corto; errores se registran en log
  sin credenciales y no lanzan (el keepalive nunca tumbaría el servicio).
- `keepalive_loop(stop_event, *, url, interval_seconds=540, client_factory)`: bucle hasta
  `stop_event`, cancelable en el shutdown del lifespan (igual que `bot_task`).

### `main.py` (lifespan)
Además de lo existente: `if settings.keepalive_url: task = create_task(keepalive_loop(...))`
y parada coordinada en el shutdown. CORS: `allow_origins=settings.cors_origins` (lista).

### `tests/test_workflows.py` (texto de los YAML, sin red)
- `daily-report.yml`: cron `0 8 * * *` + `workflow_dispatch`; `pip install -r
  requirements.txt`; ejecuta `send_daily_report.py`; `DATABASE_URL`/`SMTP_USER`/`SMTP_PASS`/
  `REPORT_TO` desde `secrets.`; `permissions: contents: read`; job ≤3 min.
- `pages.yml`: `actions/configure-pages`, `actions/upload-pages-artifact` sobre `frontend/dist`,
  `actions/deploy-pages`, build con `npm ci && npm run build`.
- Seguridad: ninguno contiene `ALLOW_LIVE_TRADING` ni `echo ${{ secrets`.
- `render.yaml`: `plan: free`, `rootDir: backend`, `healthCheckPath: /health`,
  `startCommand` con `uvicorn app.main:app`, env `SIMULATION_BOT_ENABLED=true`,
  `DATABASE_URL`/`API_TOKEN`/`CORS_ORIGINS`/`KEEPALIVE_URL` con `sync: false`.

### `tests/test_database_postgres.py` (sin servidor PG)
- `CreateTable` compilado con `postgresql.dialect()` para cada tabla de `Base.metadata`
  (falla si un tipo no es portable).
- El engine de `app.database` con `DATABASE_URL=postgresql://…` no registra los guards
  de SQLite (verificar la rama condicional sin conectarse: usar `create_engine` con
  `strategy`... si no es posible sin driver, se valida la función de guard directamente).

## Configuración (M2/M6) — `app/config.py`

| Var | Default | RF |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | RF-7 |
| `SMTP_PORT` | `587` | RF-7 |
| `SMTP_USER` | `` (vacío) | RF-7 |
| `SMTP_PASS` | `` (vacío) | RF-7 |
| `REPORT_TO` | `` (vacío → fail-closed) | RF-4, RF-7 |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:4173` (CSV) | RF-8 |
| `KEEPALIVE_URL` | `` (vacío → desactivado; en Render: `https://<svc>.onrender.com`) | RF-1 |
| `DATABASE_URL` | `sqlite:///./crypto_bot.db` (ya existe) | RF-2 |
| `SIMULATION_BOT_ENABLED` | `false` (ya existe; `true` en Render) | RF-1 |
| `API_TOKEN` | `` (ya existe; **obligatorio** en Render → RF-4/RF-6) | RF-4, RF-6 |

`.env.example` documenta las nuevas (sin valores reales). `requirements.txt`:
`psycopg[binary]==3.2.*` (versión pineada al implementar).

## Configuración humana (fuera del código — README, M8)

1. **Neon**: crear cuenta free, proyecto, copiar el URL de conexión (pooler) → Secret `DATABASE_URL`.
2. **Render**: crear *Web Service* desde GitHub (`render.yaml` o manual), env vars
   `DATABASE_URL`, `SIMULATION_BOT_ENABLED=true`, `API_TOKEN` (generado), `CORS_ORIGINS`
   (URL de Pages), `KEEPALIVE_URL` (URL pública del servicio).
3. **Gmail**: 2FA + contraseña de aplicación → Secrets `SMTP_USER`, `SMTP_PASS`, `REPORT_TO`.
4. **Pages**: repo público → workflow `pages.yml` (o Settings → Pages → GitHub Actions);
   copiar la URL del sitio a `CORS_ORIGINS`.
5. Primer acceso: abrir el panel, introducir `API_TOKEN`, detener/arrancar y comprobar el
   primer correo (lanzar `daily-report.yml` a mano).

## Riesgos y mitigaciones

- **750 h/mes justo** (always-on = 720–744 h): el keepalive usa la URL del propio servicio;
  si Render suspende el servicio por límite, el informe diario de Actions sigue saliendo
  (D-5 + RF-5) y el servicio se reactiva al mes siguiente; documentado en README.
- **Neon suspenso por inactivity**: la primera conexión tras la pausa tarda ~1–3 s →
  `pool_pre_ping=True` en el engine PG para evitar errores transitorios.
- **Gmail bloquea login de apps**: usar contraseña de aplicación (no la normal); si el
  workflow falla, GitHub avisa por correo (complemento gratis del informe).
- **Reinicios/deploy de Render**: auto-arranque existente (H3) + create_all idempotente;
  el estado vive en Neon.
- **Cron retrasado/saltado** (GitHub lo advierte): el informe puede llegar minutos tarde —
  aceptable; reenvío manual disponible.
- **Repo hecho público para Pages**: sin secretos en el código; solo datos de paper.

## Fuera de alcance de este plan

Zona congelada de la spec 001, TESTNET/LIVE en la nube (D-6), Telegram/push, MongoDB (H6).
