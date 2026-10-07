# Fase 0 — Diagnóstico del brief "AI Trading Intelligence System"

Fecha: 2026-10-07 · Estado: **PENDIENTE DE APROBACIÓN — no implementar nada hasta que el propietario valide este documento (brief §38).**

Fuentes: `claude_master_brief_ai_trading_bot.md`, `talos_visual_analysis.json`,
`docs/constitution.md`, `specs/001…004` y el código del repositorio (inspección
directa, sin asumir arquitectura — regla §36 del brief: READ → MAP → REPORT).

---

## 1. Mapa del repositorio existente

```text
crypto-bot/
├── .github/workflows/     daily-report.yml (cron 08:00 UTC), pages.yml (deploy panel)
├── backend/               Python 3.14 · FastAPI 0.141 · SQLAlchemy 2 · Pydantic 2
│   ├── app/
│   │   ├── api/routes/    bot.py, signals.py, simulation.py, health.py + auth.py (RF-20)
│   │   ├── domain/        orb_engine.py (RF-7), signal_engine.py (RF-15), risk_math.py
│   │   ├── services/      26 módulos (loop, ejecución, riesgo, decisiones, backtest…)
│   │   ├── models.py      12 tablas · config.py (44 settings .env) · main.py (lifespan)
│   ├── tests/             37 ficheros · 6.710 líneas · unittest (sin red, RNF-2)
│   ├── train_strategy.py, collect_klines.py, send_daily_report.py, check_binance_testnet.py
│   ├── requirements.txt   10 dependencias pinneadas (constitución #12)
│   └── README.md          documentación operativa
├── frontend/              React 19 · Vite 8 · axios · vitest 5 (69 tests) · eslint
│   └── src/               App.jsx + 14 componentes + 1 página (3.253 líneas)
├── specs/                 001 bot spot (v3 ORB, completa) · 002 nube/informe · 003 panel · 004 informe HTML
├── docs/                  constitution.md (13 reglas)
└── render.yaml            Render free + healthcheck /health
```

Volumen: backend `app/` 9.632 líneas · tests backend 6.710 · frontend 3.253.
Ramas: trabajo todo en `master` (últimos commits: spec 003, spec 004, "Update").

## 2. Arquitectura actual

Monolito modular (cartera de servicios + router REST + SPA estática), sin workers
externos ni colas. Flujo real hoy:

```text
lifespan (main.py, si SIMULATION_BOT_ENABLED=true)
  └─> bot_loop.run(stop_event)                      [RF-3 kill switch, RF-22 breaker]
        ├─ descarga klines 15m (8 pares) + 5m en ventana ORB (4 pares)   [RF-6]
        ├─ risk_guard: pérdida diaria, aperturas/día, cooldown            [RF-4/RF-5]
        ├─ señales externas con TTL/precio/duplicados (panel/webhook)     [RF-8/RF-9]
        ├─ evaluate_orb → BUY/HOLD, 1 decisión técnica por par por día NY [RF-7/RF-27]
        ├─ decisión → snapshot → execution (paper o Binance)              [RF-10]
        └─ order_lifecycle: fill → stop/tp → cierre, PnL, incidentes      [RF-13/RF-24]
API REST (FastAPI)  ── estado/métricas/fase/kill switch/señales/auditoría
Frontend (React)    ── panel 3 columnas oscuro: EquityChart, métricas, kill switch,
                       formulario copy, historial, precios
Persistencia        ── SQLite local / Neon Postgres en nube
Backtest (offline)  ── strategy_lab_service + train_strategy (grid, splits, ORB)
```

Fases máquina actuales: `SIMULATION → TESTNET → LIVE` con gates (RF-16) y doble
confirmación `ALLOW_LIVE_TRADING` + `CONFIGURED_CAPITAL_USD` (RF-1/RF-2).

## 3. Inventario de integraciones

| Integración | Uso | Estado |
|---|---|---|
| Binance REST público (`api.binance.com`) | klines, exchangeInfo, ticker (sin claves) | **Activa** (RF-6) |
| Binance Spot Testnet (`testnet.binance.vision`) | órdenes de prueba | Activa, manual (T20) |
| Binance Spot producción | órdenes reales | Cableada, **dormida** (RF-1/RF-14, claves vacías) |
| OKX Demo + arbitraje multi-exchange | legado | **Congelado** (RF-21, SHA-256 verificado) |
| SMTP Gmail | informe diario | Activa (spec 002 RF-3) |
| Render free | API + loop 24/7 | Activa (keepalive RF-1) |
| Neon free (Postgres) | BD persistente | Activa (spec 002 RF-2) |
| GitHub Actions | informe diario + deploy panel | Activa |
| GitHub Pages | panel estático | Activa (CORS RF-8) |
| LLM (Gemini u otro) | analista IA | **No existe** |
| Noticias / CoinGecko / DefiLlama / Fear&Greed | contexto | **No existen** |
| Order book, funding, open interest, opciones | microestructura/derivados | **No existen** |

Nota: `talos_visual_analysis.json` cita 3 PNG de referencia que no están en el repo
(solo está el análisis textual).

## 4. Inventario de variables de entorno

Backend (`app/config.py`, 44 settings, todos con defecto seguro):

| Grupo | Variables |
|---|---|
| Núcleo | `APP_NAME`, `APP_VERSION`, `DATABASE_URL`, `SKIP_DB`, `MONGO_URI` (legado) |
| Simulación legado | `SIMULATION_INITIAL_BALANCE`, `SIMULATION_FEE_RATE`, `SIMULATION_BOT_*` (10) |
| Fase 1 (001) | `ALLOW_LIVE_TRADING`, `CONFIGURED_CAPITAL_USD`, `API_TOKEN`, `TRADING_SYMBOLS`, `ORB_SYMBOLS`, `TRADING_INTERVAL_SECONDS`, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`, `MAX_SIGNAL_PRICE_DISTANCE_PCT`, `SIGNAL_TTL_SECONDS` |
| Binance | `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `BINANCE_TESTNET_BASE_URL`, `BINANCE_RECV_WINDOW_MS`, `BINANCE_MARKET_DATA_BASE_URL` |
| OKX (congelado) | `OKX_DEMO_API_KEY/SECRET/PASSPHRASE/BASE_URL/TIMEOUT_SECONDS` |
| Informe | `SMTP_HOST/PORT/USER/PASS`, `REPORT_TO` |
| Nube | `KEEPALIVE_URL`, `CORS_ORIGINS` |

Frontend: `VITE_API_URL` (variable de repo en GitHub). GitHub Secrets: `SMTP_USER`,
`SMTP_PASS`, `REPORT_TO`. Render: `DATABASE_URL`, `API_TOKEN`, `CORS_ORIGINS`,
`KEEPALIVE_URL`, `SIMULATION_BOT_ENABLED=true` (secretos con `sync: false`).
**No hay claves de LLM ni de proveedores de datos.** Todas las claves viven en
`.env`/secretos fuera de git (RNF-4).

## 5. Inventario de riesgos

**Financieros**
1. Riesgo de gap en el stop (volatilidad > 0.5% de slippage permitido, RF-24 solo registra).
2. Bloqueo de capital por mínimo notional de Binance (mitigado: RF-11 lo consulta).
3. Exchange caído/rate limit → fail-closed y circuit breaker (RF-22, RNF-6) — mitigado.
4. Capital minúsculo (20 USD): cualquier fee no modelada invalida las métricas (mitigado en backtest, RF-15).

**Seguridad**
5. Sin rate limiting en la API (0 coincidencias en código): el panel y el webhook dependen de `API_TOKEN`/`?token=`; en `SIMULATION` el token es opcional (RF-20).
6. Claves de exchange sin política documentada de rotación/IP whitelist (el brief §26 la exige para live).
7. Password de Gmail como app-password en GitHub Secrets (correcto, pero sin rotación documentada).
8. La clave de Gemini (futura) debe vivir solo en backend (brief §19).

**Técnicos**
9. `client.test.js` flaky observado (1 timeout en 3 ejecuciones) → estabilidad de CI.
10. Zona congelada envejeciendo (8 ficheros + 3 dependencias sin mantener, por diseño RF-21).
11. `simulation_initial_balance`/`simulation_fee_rate` siguen como `float` en config (legado pre-001; conversión a `Decimal` pendiente de confirmar en cada uso).
12. Reconciliación bot↔exchange: solo se menciona en `bot_loop`; la spec exige reconstruir estado tras corte de proceso (caso límite) — alcance a confirmar en la spec de observabilidad.

**Proceso**
13. Brief §34 exige diagnóstico aprobado antes de implementar: este documento es ese gate.
14. Conflicto estructural: el brief pide shorts/long-short y 11 símbolos; la constitución #1 y D-13 los descartan para la fase 1 → requiere decisión explícita del propietario.

## 6. Gap analysis contra el brief

Estado: ✅ cubierto · 🟡 parcial · ❌ ausente · ⛔ conflicto con constitución/spec.

| Brief | Estado | Notas |
|---|---|---|
| §1 Vista equity curve + operaciones | 🟡 | `EquityChart` + historial existen; faltan drawdown/expectancy/profit factor/Sharpe/PnL por activo, operación seleccionable → timeline |
| §2-§3 Control room (nodos, eventos) y memoria (hipótesis vs conocimiento) | ❌ | nada equivalente hoy |
| §4 Long/short + universo dinámico 11 símbolos | ⛔ | Spot sin cortos (constitución #1, D-13); 8 pares fijos (D-3) |
| §5 Contexto multidimensional (order book, derivados, noticias, liquidez) | ❌ | solo OHLCV + ticker |
| §6-§7 Analista IA (Gemini, I/O estructurado, separado de ejecución) | ❌ | bucle 100% determinista (ORB) |
| §8 Motor de riesgo independiente (exposición, correlación, resize/block) | 🟡 | existe `risk_guard`/`risk_math`: pérdida diaria, aperturas, cooldown, sizing 25%, 3 posiciones, tope 1 USD — falta exposición total/por dirección/correlación y veto estilo ORDER RESIZED/BLOCKED |
| §9 Coste de oportunidad de cartera | ❌ | |
| §10 Backtest determinista (walk-forward, funding, fills parciales) | 🟡 | ✅ fees 0.1%/lado, slippage, splits train/valid/test sin look-ahead, grid, backtest ORB con TP/SL (RF-15); ❌ walk-forward, funding, fills parciales, liquidez |
| §11 Replay de decisiones | 🟡 | cada decisión guarda snapshot+resultado (RF-10); ❌ UI de replay y reconstrucción puntual |
| §12-§16 UI Control Room (header, agresividad, canvas, why, timeline) | 🟡 | panel real 3 columnas oscuro con métricas, kill switch, equity, historial, copia; ❌ canvas de nodos, panel "Why?", modos/estados, stream de eventos |
| §17 Aprendizaje con estados (PROPOSED→…) y rollback | ❌ | |
| §18-§24 Fuentes (exchange ✅, CoinGecko, DefiLlama, F&G, noticias, grounding) | 🟡 | exchange ✅; resto ❌ |
| §25-§26 Secretos en `.env`/secretos, sin claves en código | ✅ | verificado (RNF-4); faltan rotación/IP whitelist/live checklist |
| §27 Observabilidad (logging estructurado, correlation ID, métricas técnicas) | 🟡 | 8 loggers, sin JSON estructurado ni correlation IDs ni coste IA; métricas de negocio ✅ |
| §28 Arquitectura modular con adapters | ✅🟡 | ya es modular por servicios; faltan etapas DATA→FEATURES→CANDIDATE→AI→RISK como módulos |
| §29 Persistencia amplia (events, news, hypotheses, versions) | 🟡 | 12 tablas de negocio ✅; faltan eventos, hipótesis, versiones de prompt/modelo |
| §30 Modos OFFLINE/PAPER/SHADOW/LIVE/EMERGENCY + controles | 🟡 | SIMULATION/TESTNET/LIVE + kill switch ✅; ❌ SHADOW, PAUSED, CLOSE-ONLY, EMERGENCY |
| §31 Validación en cascada + reconciliación periódica | 🟡 | cadena existente evaluar→riesgo→ejecutar ✅; reconciliación periódica automática ❌ |
| §32 Kill switch independiente del LLM | ✅ | RF-3, botón en panel |
| §33 VPS (despliegue posterior) | 🟡 | hoy Render free; VPS pendiente (brief la pospone hasta después de la auditoría) |
| §35 Reglas de diseño (sin humo, estados reales) | ✅🟡 | panel actual cumple; control room debe heredar el sistema de diseño de `talos_visual_analysis.json` |
| §36 READ→MAP→… sin reescrituras | ✅ | este documento |
| §38 Los 19 entregables | ✅ | este documento |
| §39 Checklist de API keys por necesidad | ✅ | §10 abajo |
| §40-§41 Seguridad de claves + principio final | ✅ | recogidos en §13 |

**Conflictos que requieren decisión del propietario (no se tocan sin aprobación):**
shorts/futuros (⛔ constitución #1), universo dinámico de símbolos vs D-3,
modos SHADOW/EMERGENCY nuevos, datos de derivados (ver decisión D-B2 abajo).

## 7. Arquitectura propuesta (evolutiva, sin reescribir)

Principio §36: conservar lo que funciona; **cada pieza nueva entra por spec propia,
con TDD y la suite en verde**. Nada de esto se implementa hasta aprobación.

```text
EXISTENTE (se conserva y extiende)
  bot_loop · risk_guard · decision_store · order_lifecycle · strategy_lab · panel React
NUEVAS ETAPAS (specs futuras, módulos nuevos en backend/app/)
  [005] observabilidad: eventos estructurados + correlation ID + health de fuentes
  [006] data & context: adapters order_book/derivados/noticias (intercambiables,
        degradación controlada "no disponible" — brief §5 "no inventar datos")
  [006] feature_engine + candidate_engine (scores explicados, brief §Fase 2-3)
  [007] ai_analyst: cliente Gemini con timeout/retries/rate-limit/breaker/cache,
        I/O JSON estructurado, coste por consulta — RECOMENDACIÓN NUNCA EJECUCIÓN
  [008] risk_engine v2: envuelve al risk_guard actual; expone BLOCKED/RESIZED con
        motivo, exposición total/dirección/activos, correlación, coste de oportunidad
  [009] UI control room: canvas de nodos con estados reales, panel Why?, replay,
        equity extendido (sobre eventos de [005], sin datos falsos)
  [010] learning: hipótesis (PROPOSED→…) vs conocimiento validado, auditables
  [011] shadow mode: máquina de estados ampliada (sin transición silenciosa a LIVE)
  [012] (condicional) futuros/shorts → exige cambio de constitución aprobado
```

Contrato invariante (brief §7): `DATA → FEATURES → FILTER → AI → RISK → EXECUTION`;
el LLM nunca toca órdenes; el risk engine puede vetar/ redimensionar y la UI lo muestra.

## 8. Roadmap por fases (brief §34 → proceso por specs)

| Fase brief | Contenido | Spec propuesta | Gate de salida |
|---|---|---|---|
| 0 Auditoría | **Este diagnóstico** | — (en `docs/`) | Aprobación del propietario |
| — | Cierre paralelo: paper-trading 30 días (RF-16 en curso con ORB) | 001 (hecha) | ≥30 días, ≥15 ops, PnL>0, dd≤10% |
| 1+2 Data + Features | adapters de datos ampliados, feature engine, health de fuentes | 005 y 006 | datos normalizados con tests mockeados |
| 3 Candidate engine | universo con filtros y scores explicados | 006 (inc.) | score por símbolo auditable |
| 4 News/context | RSS/noticias con deduplicación y sentimiento | 006 (inc.) | señal estructurada de prueba |
| 5 AI analyst | Gemini recomendación-only | 007 | I/O validado, coste trazado, sin ejecución |
| 6 Risk engine | v2 con veto/redimensión | 008 | property tests de límites |
| 7 Paper | con la estrategia activa (ORB) — ya existe el soporte | 001 | métricas reales |
| 8 Replay + backtest | replay UI + walk-forward | 009 (inc.) | decisión reproducible |
| 9 Learning | hipótesis/conocimiento | 010 | estados + rollback |
| 10 UI Control Room | consola completa | 009 | usabilidad: todo rastreable |
| 11 Shadow | "qué habría hecho" vs mercado | 011 | comparativa diaria |
| 12 Live | ya protegido por RF-1/RF-2/RF-16 + gates del brief | 001 | todos los gates verdes |

**Dependencias:** 005 → 009 y 010 (sin eventos no hay canvas ni replay);
006 → 007 (contexto primero); 008 antes de cualquier recomendación con tamaño.

## 9. Nuevas dependencias (lista exacta)

- **Obligatorias: NINGUNA.** Gemini se consume por REST con `httpx` (ya presente);
  logging estructurado con `logging` de stdlib (serialización JSON propia).
- Opcionales (solo si la spec correspondiente lo justifica, constitución #12):
  `feedparser` (parseo RSS, spec 006), `redis` (rate-limit compartido — hoy innecesario),
  SDK `google-genai` (innecesario frente a REST con httpx).
- Prohibido: añadir servicios externos no declarados.

## 10. API keys realmente necesarias (checklist §39)

| Clave | Veredicto | Cuándo |
|---|---|---|
| `BINANCE_API_KEY/SECRET` (testnet) | **NECESARIA** (ya creada) | fases testnet/real de 001 |
| Claves de producción Binance (permisos Spot, **retiros desactivados**, IP whitelist) | **NECESARIA** | solo al pasar a LIVE (RF-16) |
| `GEMINI_API_KEY` + modelo | **RECOMENDADA** | spec 007 |
| GNews / NewsAPI | **OPCIONAL** | spec 006 (empezar por RSS público gratis) |
| CoinGecko Demo API | **OPCIONAL** | spec 006 (enriquecimiento, nunca decisión) |
| Alternative.me Fear&Greed | **NO NECESARIA CLAVE** (API abierta) | spec 006, feature contextual |
| DefiLlama | **NO NECESARIA** | solo si hay foco DeFi (hoy no) |
| Etherscan / Alchemy / QuickNode / proveedores de opciones | **NO NECESARIA** | fuera del alcance Spot Binance |
| Redis / VPS SSH | **NO NECESARIA** aún | VPS cuando se escale (§33) |

Reglas: nunca en código ni frontend; solo backend/`.env`/secretos; rotación al
terminar el experimento si alguna se comparte por chat (brief §40).

## 11. Coste mensual en modo paper

| Parte | Coste |
|---|---|
| Render free (API + loop) | 0 USD (límite 750 h; el servicio usa ~744 h) |
| Neon free (Postgres) | 0 USD |
| GitHub Actions (informe) + Pages (panel) | 0 USD |
| Binance API (público + testnet) | 0 USD |
| SMTP Gmail | 0 USD |
| Gemini (tier gratuito de modelos, ≤4 consultas/día) | 0 USD estimado; si se excede el free tier y se activa pago: **≤5 USD** |
| **Total paper** | **0 USD** (peor caso: ~5 USD con Gemini de pago) |

## 12. Coste mensual en modo live

- Infraestructura: mismos 0 USD (mismos tiers gratis).
- Comisiones Binance Spot (0.1% por lado, market order): con 20 USD aportados y
  ~1 operación/día de riesgo ≤1 USD → **≈0.6–1.5 USD/mes** en fees (ya descontadas
  en el PnL de la spec; D-9 exige PnL neto).
- Deslizamiento real: modelado en backtest (0.05%/lado por defecto) — no es coste
  fijo.
- Escalonado opcional: Render pagado (7 USD/mes) si se supera el límite de horas;
  VPS (brief §33) cuando aporte algo que Render no dé.
- **Total live estimado: 0 USD de infraestructura + fees de trading.**

## 13. Plan de seguridad

Ya existe: secretos solo en `.env`/secrets (RNF-4), `ALLOW_LIVE_TRADING` +
`CONFIGURED_CAPITAL_USD` + fase LIVE (RF-1/RF-2), `API_TOKEN` en rutas que operan
(RF-20), webhook con token (RF-8), kill switch (RF-3), zona congelada con hash,
suite sin credenciales (RNF-2).

Añadir (specs futuras):
1. Checklist de clave live: permisos Spot únicamente, **retiros desactivados**,
   IP whitelist si Binance la permite, límite de capital, kill switch probado.
2. Rotación documentada de claves (exchange, Gemini, SMTP) con fecha en el runbook.
3. Rate limiting en API + webhook (hoy 0) — mínimo por IP/token.
4. Nunca imprimir claves/tokens en logs (auditoría de `print`/logger al añadir
   observabilidad); prompt y respuestas del LLM sin secretos.
5. Modo `CLOSE-ONLY`/`EMERGENCY` como RF nuevos (brief §30/§32) — con spec.

## 14. Plan de observabilidad

Hoy: 8 loggers puntuales, métricas de negocio en `/api/bot/metrics`, `/health`,
informe diario. Falta el estándar del brief §27.

1. Logging JSON por evento: `timestamp UTC, level, service, asset, correlation_id,
   event_id, strategy_version, model_version, mode, latency, result`.
2. Correlation ID por ciclo de decisión → unión con `SignalDecision` (RF-10) para
   replay (§11) y panel "Why?".
3. Tabla `system_events` (nuevo modelo) con retención por niveles (§29).
4. Métricas técnicas expuestas: latencia de datos/IA/ejecución, errores API, uso de
   rate limit, coste IA acumulado, fuentes stale.
5. Health de fuentes: `HEALTHY/DEGRADED/STALE/ERROR/DISABLED` por nodo (base del
   canvas de la UI, sin animaciones falsas).
6. Nunca registrar secretos (ver §13.4).

## 15. Plan de datos

Hoy: 12 tablas (señales, posiciones, incidentes, riesgo diario, fases, runtime +
tablas de simulación/legado) + JSONL de klines locales.

1. Nuevos modelos: `market_snapshots_seleccionados`, `features`,
   `candidates`, `ai_evaluations`, `risk_decisions`, `events`,
   `news_events`, `hypotheses`, `knowledge`, `strategy_versions`,
   `prompt_versions`, `model_versions` (brief §29).
2. Retención por niveles: ticks/features 7–30 días, decisiones y trades indefinidos,
   agregados diarios para siempre (evitar coste de almacenar cada tick).
3. Klines 5m/15m como dataset versionado para backtest (ya con `collect_klines.py`).
4. Adaptadores de datos con interfaz intercambiable (`NewsProvider`, `DataSource`)
   y degradación explícita "no disponible" — nunca inventar datos (§5).
5. Timestamps siempre UTC naive en dominio (convención actual) + `America/New_York`
   solo en ORB.

## 16. Plan de UI

Base: panel actual (React 19, 3 columnas, oscuro, EquityChart, métricas, kill
switch, formulario de copia, historial) + sistema de diseño de
`talos_visual_analysis.json` (paleta near-black navy, verde/rojo/ámbar/cian,
animar solo eventos reales, timestamps obligatorios).

Evolución (spec 009), sin rehacer lo existente:
1. Header extendido: PnL diario/total, drawdown, operaciones, consultas y coste IA,
   salud de fuentes, estados de modo reales.
2. Equity curve mejorada: marcadores por operación seleccionable → timeline de
   decisión (§15 del brief).
3. Canvas de nodos con **nodos reales** del pipeline y estados/latencias reales
   (los mismos health checks de §14); clic → payload resumido.
4. Panel "Why?" por decisión: factores a favor/en contra, riesgo, decisión
   (alimentado por `ai_evaluations` + snapshot, no por texto inventado).
5. Vista replay: decisión de la BD → reconstrucción del contexto en ese instante.
6. Pestaña Learning (hipótesis amarillo vs conocimiento verde) cuando exista 010.
7. Prohibiciones del brief §35: sin cards decorativas, sin "thinking" falso, sin
   métricas sin timestamp, todo botón con backend real.

## 17. Plan de testing

Mantener (lo que ya funciona): TDD estricto, "RF sin test = no implementado",
suite diaria sin red/credenciales (mock `httpx`), `Decimal` obligatorio, ruff,
eslint, vitest, compileall, test de zona congelada por hash.

Añadir por spec:
1. Contratos de I/O del LLM con respuestas mockeadas (JSON estricto, reintentos,
   breaker, coste calculado) — sin llamadas reales en la suite.
2. Tests de degradación: fuente caída → "no disponible" + decisión degradada.
3. Property tests del risk engine v2 (invariantes: ≤1 USD/operación, ≤5% diario,
   exposición ≤ límites).
4. Replay: reconstruir una decisión guardada == contexto original.
5. Estabilidad: eliminar el flaky de `client.test.js` observado en Fase 0.
6. Backtest como gate de estrategia (split temporal, sin look-ahead) antes de
   cualquier cambio de parámetros (ya es RF-15; extender a walk-forward en 009).

## 18. Plan de deployment

Hoy: Render free (`render.yaml`, healthcheck `/health`) + Neon + GitHub Actions
(informe) + GitHub Pages (panel). Sin Docker; sin SSH en el repo.

1. Mantener Render hasta que límites gratuitos o el brief §33 (VPS) lo justifiquen.
2. VPS posterior: SSH y claves **fuera** del repo (brief §33/§40); checklist de
   despliegue = inspeccionar repo, tests, paper mode, healthchecks (ya cumple §33).
3. Variables nuevas (p. ej. `GEMINI_API_KEY`) → secretos de Render/Actions, nunca
   en `render.yaml` en claro ni en el frontend.
4. CI mínima por PR: `unittest` + `ruff` + `vitest` + `eslint` (hoy solo cron de
   informe y deploy; añadir workflow de verificación es barato y cubre el gate
   "nunca en rojo").
5. Staging = SIMULATION; transiciones de fase solo por API con token (RF-20).

## 19. Criterios de aceptación por fase

| Fase | Criterios de aceptación |
|---|---|
| 0 (ahora) | Diagnóstico leído y **aprobado**; decisiones D-B1…D-B6 contestadas |
| 005 Observabilidad | Eventos JSON con correlation ID; health de fuentes visible; cero secretos en logs; tests verdes |
| 006 Data/Features/Candidates/News | Adaptadores con mock; features deterministas; score explicado por símbolo; noticias deduplicadas; degradación "no disponible" testeada |
| 007 AI analyst | I/O JSON validado; timeout/retries/rate-limit/breaker/cache; coste por consulta registrado; **solo recomendación** (ninguna orden nace del LLM); tests con Gemini mockeado |
| 008 Risk v2 | Invariantes de la constitución verificadas por tests; respuestas BLOCKED/RESIZED auditables; UI las muestra |
| 009 UI + Replay | Toda decisión rastreable de punta a punta; canvas con estados reales; sin animaciones/decoración falsa; equity con métricas del brief |
| 010 Learning | Hipótesis no puede autoactivarse; estados y rollback auditables |
| 011 Shadow | Comparativa diaria "bot vs mercado" durante ≥30 días sin dinero real |
| 012 Live (ya regulado por 001) | RF-16 completa: ≥30 días paper, ≥15 ops, PnL>0 neto, dd≤10%, backtest + en valid y test, `ALLOW_LIVE_TRADING=true`, kill switch probado |

---

## Decisiones que requieren aprobación del propietario

- **D-B1 · Shorts/futuros (brief §4):** ⛔ hoy descartados por la constitución #1.
  ¿Aplazar a spec 012 condicional, o cambiar la constitución?
- **D-B2 · Datos de derivados (funding/OI):** la API de *futuros* de Binance sí los
  publica; **leer** datos de futuros sin operarlos ¿encaja en "solo Spot"?
- **D-B3 · Universo dinámico de símbolos** (brief §4) frente a D-3 (8 pares fijos).
- **D-B4 · Gemini como primer LLM** (brief §19) y presupuesto tolerable (0–5 USD/mes).
- **D-B5 · Orden de ejecución:** ¿primero 005 (observabilidad, base de todo) como
  propone el roadmap, o prefieres atacar otro hueco primero?
- **D-B6 · Prioridad frente a RF-16:** el paper de 30 días de la spec 001 sigue en
  paralelo; las specs nuevas ¿coexisten sin tocar el loop en producción?

**Próximo paso tras tu aprobación:** escribir la spec 005 (observabilidad) con RF, plan
y tasks siguiendo el proceso SDD actual — sin código hasta que esa spec esté aprobada.
