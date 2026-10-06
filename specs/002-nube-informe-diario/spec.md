# Spec 002 — Bot en la nube gratis (Render) + informe diario por correo

**Estado: borrador v2 — pendiente de aprobación.** (v1 descartada: Actions-como-bot +
BD versionada en git; ver `clarificacion.md` §A.)
Fecha: 2026-10-05 · Depende de: spec 001 (completa, T1–T20) · Constitución: `docs/constitution.md`

## Contexto y objetivo

El bot de la spec 001 está validado en local (fase SIMULATION, suite en verde, testnet
comprobado el 2026-10-05). Esta spec lo lleva a la nube **sin coste alguno**: el backend
corre **24/7 en Render free** con persistencia en **Postgres gratis (Neon)**, el **informe
diario** sale por **Gmail SMTP desde GitHub Actions** (Render free bloquea el SMTP) y el
**panel** se publica en **GitHub Pages**. La spec 001 dejó el correo fuera de alcance
(RF-18: «notificar = mostrar en panel»); esta spec lo habilita.

## Alcance

**Dentro:**
- Ejecución continua en Render free: auto-arranque del bucle + keepalive antispin-down.
- Persistencia dual: Postgres (despliegue) / SQLite (tests locales) sobre SQLAlchemy.
- Construcción del informe diario + envío por Gmail SMTP (stdlib) ejecutado desde Actions.
- CLI de informe (manual/reintento) y configuración de correo por env vars.
- CORS configurable + frontend preparado para Pages (API URL y token de control).
- Workflows: `daily-report.yml` y `pages.yml`; `render.yaml` (blueprint).
- Documentación de puesta en marcha (Neon, Render, Secrets, Pages, Gmail 2FA).

**Fuera de alcance:**
- Fases TESTNET/LIVE en la nube (siguen esperando los criterios RF-16).
- Notificaciones Telegram/push.
- Cambios en la zona congelada de la spec 001 (RF-21 intacta).
- SMTP saliente desde Render (bloqueado por plataforma, H1) y bases de datos MongoDB.

## Requisitos funcionales

- **RF-1 — Ejecución continua en Render free.** EL SISTEMA corre como web service en Render
  (plan free) y mantiene el ciclo de trading activo: (a) el proceso arranca con
  `SIMULATION_BOT_ENABLED=true` y lanza `bot_loop` (auto-arranque existente); (b) una tarea
  de **keepalive** petitiona la propia URL pública cada ≤9 min para que el servicio no caiga
  en spin-down (15 min sin tráfico). Fase SIMULATION (D-6). Sin claves de Binance.

- **RF-2 — Persistencia en Postgres con compatibilidad verificada.** EL SISTEMA funciona
  sobre **PostgreSQL** en despliegue (`DATABASE_URL` → Neon) y sobre **SQLite** en la suite
  local, con el mismo código: los guards de dialecto (PRAGMA/foreign_keys) solo aplican a
  SQLite, los modelos y consultas compilan en ambos dialectos, y `psycopg[binary]`
  pineado en `requirements.txt`. Se verifican sin servidor mediante test de compilación de
  esquemas con el dialecto `postgresql`.

- **RF-3 — Informe diario por correo.** EL SISTEMA envía cada día a las **08:00 UTC** un
  correo en español (texto plano) a `settings.report_to` con, como mínimo: fecha (UTC),
  fase, estado del bot (activo/detenido/bloqueado + motivo), balance disponible, valor de
  posiciones, balance total, PnL realizado y no realizado, drawdown, pérdidas y aperturas
  del día (n/10), posiciones abiertas (n/3), resumen de las últimas 24 h (decisiones
  ejecutadas/rechazadas/pendientes/con error + motivos) y estado del circuit breaker.
  Las métricas provienen de `decision_store.get_metrics` (RF-17 de la spec 001).
  El envío lo ejecuta el workflow diario de GitHub Actions con el CLI `send_daily_report.py`;
  también es lanzable a mano (`workflow_dispatch` o localmente).

- **RF-4 — Secretos y fail-closed.** Las credenciales viven **solo** en Render env vars
  (`DATABASE_URL`, `API_TOKEN`, `SIMULATION_BOT_ENABLED`, `CORS_ORIGINS`) o en GitHub
  Secrets (`DATABASE_URL`, `SMTP_USER`, `SMTP_PASS`, `REPORT_TO`), o en `.env` local
  (ignorado por git). Ni el código ni los workflows imprimen sus valores. Sin
  `REPORT_TO`/`SMTP_PASS` → envío rechazado con mensaje claro y sin trazas; ningún
  workflow define `ALLOW_LIVE_TRADING`.

- **RF-5 — Informe independiente del estado del bot.** El workflow del informe se ejecuta
  aunque el bot esté detenido, bloqueado o sin decisiones: lee directamente la BD (Neon) y,
  en su caso, el correo indica el estado y «sin datos» en las secciones vacías.

- **RF-6 — Kill switch remoto.** EL SISTEMA permite detener y reanudar el bot en la nube
  sin reinicio: la API pública de Render acepta `Authorization: Bearer <API_TOKEN>` en las
  rutas de control (RF-20 de la spec 001 ya lo implementa) y el bucle respeta
  `runtime.running` en ≤1 ciclo (60 s). El panel de Pages permite introducir el token y
  usar el kill switch; el flujo local sin token en SIMULATION sigue funcionando.

- **RF-7 — Configuración del correo.** Host, puerto, usuario, contraseña y destinatario son
  configurables por env vars (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`,
  `REPORT_TO`), con defaults de Gmail (`smtp.gmail.com:587`, STARTTLS); `REPORT_TO` vacío
  por defecto → fail-closed.

- **RF-8 — Panel publicable en GitHub Pages.** EL SISTEMA permite desplegar el frontend
  como sitio estático: la URL de la API es configurable en build (`VITE_API_URL`), los
  orígenes CORS son configurables por env var (`CORS_ORIGINS`, default `localhost:5173/4173`),
  el token de control se introduce en la UI (localStorage, cabecera Bearer) y **nunca** se
  embebe en el bundle estático.

## Requisitos no funcionales

- **RNF-1 — Dependencias:** única nueva `psycopg[binary]` (pineada, constitución #12);
  el correo usa `smtplib`/`email` de la stdlib; el keepalive usa `httpx` (ya presente).
- **RNF-2 — Suite sin red y sin servicios:** los tests usan SQLite en tempdir y mockean
  `smtplib`/`httpx`; la compatibilidad Postgres se verifica compilando esquemas sin
  conectarse; los YAML se validan por test de texto; nada requiere Render ni GitHub.
- **RNF-3 — Sin secretos en logs** ni en el frontend (H4): ni `print`/`echo` de valores,
  ni tokens en el bundle de Pages.
- **RNF-4 — Coste y recursos:** mantener el coste en 0 USD/mes (free: ≤750 h/mes,
  512 MB RAM, 0.1 CPU; keepalive ≤9 min; job de informe ≤3 min).
- **RNF-5 — Local primero:** la suite completa y los CLIs siguen funcionando en local con
  SQLite y sin Render/Actions/credenciales (los de correo fallan con mensaje claro).

## Decisiones

- **D-1 — Render free + keepalive propio** (propietario, 2026-10-05): web service único
  siempre despierto mediante self-ping a su URL pública (sin servicios externos de
  monitorización). Descartados: Actions-como-bot, Render pago, Oracle VM, PC+túnel.
- **D-2 — Hora del informe:** 08:00 UTC (10:00 CEST), cron de Actions; ajustable editando
  el workflow; reenvío manual con `workflow_dispatch`.
- **D-3 — Envío vía Gmail SMTP desde GitHub Actions** (`smtp.gmail.com:587`, STARTTLS,
  contraseña de aplicación): Render free bloquea el SMTP saliente desde 2025-09-26 (H1);
  Actions no lo bloquea. Servicio externo declarado (constitución #12).
- **D-4 — Persistencia en Postgres gratis (Neon)** (sustituye al commit de BD de la v1):
  cuenta free, sin expiración; SQLite se conserva para tests y uso local. Descartado
  MongoDB Atlas (H6: no hay código Mongo; migración total).
- **D-5 — Keepalive cada 9 min desde el propio proceso** para no pagar servicios de
  uptime ni despertar por reinicio: un servicio siempre encendido usa 720–744 h de las
  750 h/mes gratuitas (margen suficiente, documentado como riesgo en `plan.md`).
- **D-6 — Fase en la nube = SIMULATION** hasta que RF-16 lo permita; TESTNET/LIVE en
  Render exigirá spec nueva (claves en env vars y doble confirmación de la constitución #5).
- **D-7 — Kill switch = API con `API_TOKEN`** (Bearer) desde el panel de Pages o curl;
  se elimina el workflow manual de kill switch de la v1 (el backend ya lo soporta).
- **D-8 — Frontend en GitHub Pages**: repo **público** (requisito de Pages en cuenta
  personal), build con `VITE_API_URL` apuntando a Render, `CORS_ORIGINS` permitiendo la
  URL de Pages, token introducido por el usuario en la UI.
- **D-9 — Uso local:** por defecto `.env` apunta a SQLite (aislado); opcionalmente se puede
  apuntar `DATABASE_URL` a Neon para ver el estado real desde local. Escritura doble
  local+Render sobre la misma BD es posible pero queda documentada como uso excepcional.
