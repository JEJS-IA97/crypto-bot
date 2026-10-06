# Tasks — Spec 002 (Fase 5, v2)

Metodología TDD: test primero → rojo → implementar → verde → suite completa → marcar `[x]` → parar.

- [x] **T1** — Informe diario (construcción)
  - RF: RF-3, RF-5
  - Hecho cuando: `app/services/report_service.py` genera el texto del informe (fase, estado,
    balance/PnL/métricas RF-17, resumen 24 h, breaker; «sin datos» si no hay datos) y
    `tests/test_report_service.py` pasa con BD en tempdir y `Decimal` intactos.
    *(Test RED ya escrito.)*
  - Tests: `tests/test_report_service.py`

- [x] **T2** — Envío de correo + configuración
  - RF: RF-4, RF-7
  - Hecho cuando: `app/config.py` expone `SMTP_HOST/PORT/USER/PASS` y `REPORT_TO` (defaults
    de Gmail, vacíos donde toca), `app/services/email_service.py` envía vía `smtplib` y sus
    tests mockéan el SMTP (sin red); sin credenciales → error claro sin trazas.
  - Tests: `tests/test_email_service.py` + `tests/test_config.py` (ampliado)

- [x] **T3** — CLI del informe
  - RF: RF-3, RF-4, RF-5
  - Hecho cuando: `send_daily_report.py` crea esquema si falta, construye y envía; lee
    `DATABASE_URL` del entorno; sin `REPORT_TO` o `SMTP_PASS` → `SystemExit` con mensaje
    claro; con BD vacía envía «sin datos».
  - Tests: `tests/test_send_daily_report.py` (SMTP y BD mockeados/tempdir)

- [x] **T4** — Compatibilidad Postgres (dual con SQLite)
  - RF: RF-2
  - Hecho cuando: `psycopg[binary]` pineado en `requirements.txt`, `app.database` registra
    los guards solo en dialecto SQLite y `tests/test_database_postgres.py` demuestra sin
    servidor que el esquema completo compila con `postgresql.dialect()` y que los guards
    no se aplican a PG.
  - Tests: `tests/test_database_postgres.py`

- [ ] **T5** — Keepalive antispin-down
  - RF: RF-1
  - Hecho cuando: `app/services/keepalive_service.py` (should_keepalive / run_ping /
    keepalive_loop a 540 s) y `main.py` lanza/param la tarea según `KEEPALIVE_URL`;
    tests con `httpx` mockeado (sin red) incluyendo url vacía, error de red y shutdown.
  - Tests: `tests/test_keepalive_service.py`

- [ ] **T6** — CORS configurable + token y API URL en el panel
  - RF: RF-6, RF-8
  - Hecho cuando: `CORS_ORIGINS` (CSV) alimenta el middleware de `main.py` (test de
    preflight con origin configurado), el cliente frontend usa `VITE_API_URL` (default
    local) y añade `Authorization: Bearer` cuando hay token en localStorage, y el panel
    permite introducir el token.
  - Tests: `tests/test_cors.py` + tests vitest del cliente frontend

- [ ] **T7** — Despliegue: render.yaml y workflows de GitHub
  - RF: RF-1, RF-3, RF-4, RF-8
  - Hecho cuando: existen `render.yaml` (blueprint free, env vars, `sync: false` en
    secretos), `.github/workflows/daily-report.yml` (cron `0 8 * * *` + dispatch, Secrets,
    `contents: read`) y `.github/workflows/pages.yml` (build y deploy a Pages), y
    `tests/test_workflows.py` verifica por texto crons, Secrets, permisos y la ausencia de
    `ALLOW_LIVE_TRADING`/`echo secrets`.
  - Tests: `tests/test_workflows.py`

- [ ] **T8** — Documentación de puesta en marcha y validación final
  - RF: todos
  - Hecho cuando: `backend/README.md` documenta los5 pasos humanos (Neon, Render con env
    vars, Gmail 2FA + contraseña de aplicación, Pages + CORS, primer correo) y la recorrida
    RF por RF de la spec 002 confirma el test de cada requisito con la suite en verde.
  - Tests: suite completa + revisión

---

## Reglas para marcar una tarea como hecha

1. Tests escritos **antes** del código de producción.
2. Suite completa en verde.
3. Salida de tests adjunta en el mensaje al usuario.
4. RF asociados verificados.
5. Solo entonces: `[x]` y parar.
