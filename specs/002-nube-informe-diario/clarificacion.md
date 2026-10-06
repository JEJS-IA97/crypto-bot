# Clarificación — Spec 002 (Fase 3, v2)

Entrevista con el propietario (2026-10-05) y hallazgos técnicos previos a `spec.md`.
La v1 (bot en GitHub Actions + BD versionada en git) fue descartada por el propietario
tras la investigación de hosting: **todo gratis y con backend en Render**.

## A. Decisiones del propietario (entrevista)

| # | Pregunta | Decisión |
|---|---|---|
| 1 | ¿Dónde corre el bot 24/7? | **Render free** (web service único). Se descartan: Actions-como-bot (v1), Render pago (~7 $/mes), Oracle VM, PC+túnel. |
| 2 | ¿Dónde persiste la BD? | **SQLite no sirve** (filesystem efímero en Render free). El propietario propuso Mongo Atlas; aclarado que **Mongo no existe en el código** (solo `MONGO_URI=` vacío en `.env.example`) y migrar = reescribir todo → se elige **Postgres gratis (Neon)**, compatible SQLAlchemy con migración media. |
| 3 | ¿Cómo sale el informe diario si Render free **bloquea el SMTP saliente** (puertos 25/465/587 desde 2025-09-26)? | **Gmail SMTP desde GitHub Actions**: un workflow diario conecta a Neon y ejecuta el CLI de informe (Actions sí permite 587). Mantiene la elección original de Gmail + contraseña de aplicación. |
| 4 | ¿Frecuencia y destino del correo? | **Diario** a `jose.e.jimenez.s.97@gmail.com`, a las **08:00 UTC**. |
| 5 | ¿Dónde vive el panel (frontend)? | **GitHub Pages** (repo debe ser público). Habla con la API de Render (CORS configurable) y lleva campo para el token de control. |

## B. Hallazgos técnicos y cómo se resuelven

- **H1 [ALTA] — Render free bloquea el SMTP saliente** (changelog 2025-09-16, activo desde
  2025-09-26; puertos 25/465/587). → **D-3**: el informe sale desde GitHub Actions, no desde
  Render. El resto de salidas de Render (Neon 5432, Binance 443, self-ping 443) sí funcionan.
- **H2 [ALTA] — Filesystem efímero en Render free**: `crypto_bot.db` desaparece en cada
  reinicio/deploy; no hay disco persistente ni background workers en el plan gratis.
  → **D-4**: Postgres externo gratis (**Neon**); SQLite queda para la suite local.
- **H3 [MEDIA] — El auto-arranque ya existe**: `lifespan` de `main.py` lanza `bot_loop.run`
  si `settings.simulation_bot_enabled` (env `SIMULATION_BOT_ENABLED=true` en Render).
  → RF-1 solo necesita documentarlo + el keepalive (H5).
- **H4 [MEDIA] — El token no puede vivir en el frontend estático** (Pages es público).
  → RF-8: el usuario introduce el token en el panel (localStorage) y se envía como
  `Authorization: Bearer` (cabecera que `auth.py` ya acepta); CORS por env var.
- **H5 [MEDIA] — Spin-down a los 15 min sin tráfico y límite de 750 h/mes** en Render free.
  → **D-5**: keepalive propio (self-ping a la URL pública cada 9 min); un servicio siempre
  despierto consume 720–744 h/mes, dentro del límite.
- **H6 [MEDIA] — Mongo no está en el código**: grep exhaustivo (pymongo/motor/MongoClient) =
  0 resultados; solo `MONGO_URI=` vacío en `.env.example`. → Atlas descartado: el mismo papel
  lo cumple Neon sin migración total (toda la persistencia ya es SQLAlchemy).
- **H7 [BAJA] — `*.db` en `.gitignore`** deja de ser relevante (la BD ya no se versiona);
  el guard de SQLite se mantiene por higiene.
- **H8 [BAJA] — Primer arranque en Render sin esquema**: `lifespan` ya ejecuta
  `Base.metadata.create_all` (idempotente) también sobre Postgres; el informe ante una BD
  vacía emite «sin datos» en lugar de fallar.

## C. Conflicto con la constitución

Ninguno detectado:
- #6 kill switch → RF-6 (API con token ya existe; esta spec lo habilita desde el panel de Pages).
- #7 spec manda → este documento. #8 tests → mapeo RF→test en `plan.md`.
- #11 `Decimal` → métricas del informe en `Decimal`.
- #12 dependencias mínimas → única nueva: `psycopg[binary]` (driver Postgres, declarada en
  RNF-1 y pineada); `smtplib`/`email` de la stdlib para el correo.
- #13 español → cuerpo del informe y docs en español.
- La zona congelada de la spec 001 no se toca (RF-21 sigue vigente).
