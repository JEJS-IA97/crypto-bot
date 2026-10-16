# Contexto completo para Claude Code — sesión 2026-10-16

Este paquete tiene todo lo que se averiguó en la sesión de investigación del 15/16-oct-2026 (Claude en la app, enlazado a esta PC). Léelo antes de tocar código. Todo aquí es contexto, no una spec: la spec activa y la constitución siguen mandando (AGENTS.md).

## 0. Quién y qué quiere
- José (Venezuela, UTC−4). Quiere generar ganancias con trading cripto **priorizando no perder**, aprendiendo poco a poco.
- Visión del bot: que aprenda, que "piense" con ayuda de Gemini, que estudie y haga pruebas, opción de copytrading, que corra **localmente al iniciar sesión de Windows y varias veces al día** (no una sola vez).
- Considera que el frontend "se ve muy hecho por IA" y quiere rediseñarlo.
- Trabaja con método SDD (silex / anti-vibecode-sdd): una fase a la vez, aprobación humana entre fases, `[NEEDS DECISION]` cuando falte algo.
- Carpeta de trabajo general de trading: `C:\Users\default.LAPTOP-6NQ66S02\Documents\projects\claude\trading` (ahí está también el informe).

## 1. Archivos de este paquete
| Archivo | Qué es |
|---|---|
| `informe-estrategias-2026-10-16.md` | Informe final (español): evidencia de estrategias, bots/IA, copytrading, mercado oct-2026, diagnóstico del bot y **plan de 9 pasos con gates** (sección "Plan de acción priorizado con gates"). |
| `research/diagnostico_bot_y_backtest_propio.md` | Diagnóstico de primera mano del repo + backtest propio con cifras exactas + estado de la señal hoy + problemas del frontend. **La fuente más importante.** |
| `research/estrategias_con_evidencia.md` | Literatura: tendencia diaria sí; intradía, grid y reversión corta no; fees; overfitting (Deflated Sharpe, PBO). |
| `research/bots_e_ia.md` | Freqtrade/FreqAI/Jesse/Hummingbot; LLMs operando con dinero real (Alpha Arena: Gemini 2.5 Pro −45.5%); cómo usar un LLM con seguridad; Windows (Task Scheduler vs NSSM). |
| `research/copytrading.md` | Evidencia de seguidores, APIs (OKX es la única usable por bot; Binance no tiene API de seguidor), criterios de selección, Venezuela. |
| `research/mercado_oct_2026.md` | Régimen de mercado con fechas: BTC −35% bajo ATH, Fed subiendo tasas, ETF con salidas, F&G 41. |
| `walk-forward-orb-20261010.md` | Copia del reporte walk-forward ORB v1 (backend/reports está en .gitignore). |
| `scripts/backtest_tendencia_diaria.py` | Port en Python (stdlib) del backtest de referencia. Verificado: da exactamente lo mismo que el cálculo original en JS sobre datos sintéticos. Úsalo como "verdad de referencia" de la spec 013. |
| `scripts/ui-capturas.cjs` + `scripts/ui-mock.json` | Cómo se capturó el panel con Playwright interceptando la API (mock con datos reales del 16-oct). Sirve para comparar antes/después del rediseño. |
| `frontend-capturas/*.png` | Capturas del panel actual: 1440 px (Operar, Estado) y móvil 390 px. |

## 2. Hechos verificados del bot (16-oct-2026)
- Corre en SIMULATION, `running: true`, capital paper 40 USD → **39.80 USD** (PnL realizado −0.29), 5 operaciones cerradas: 4 perdedoras.
- Estrategia activa `orb-001-v3` (ORB 9:00–10:00 NY, 5m, solo largos, SL=TP=2%, filtro EMA50 1h de spec 012).
- **ORB v1 NO PASA** su walk-forward (−14.1% neto, 0/6 folds, PF 0.24, 15% aciertos, PnL bruto ≈ −2.8 USD → sin ventaja ni antes de costes). **ORB v2 nunca se evaluó** (spec 012 T9 hecho en commit 987127e pero tasks.md lo marca pendiente; T10 y T11 sin hacer). Conclusión: está corriendo una estrategia que no pasó su propio gate.
- Gemini: fuente DISABLED, 0 consultas/24 h. Pipeline: solo klines/exchangeInfo/BD sanos; order book, news, fear&greed, sentimiento, derivados, regime detector = DISABLED/stub.
- Arranque: `iniciar_bot.bat` manual (uvicorn oculto en 127.0.0.1:8000). **No hay tarea programada** de inicio de sesión. `backend/data/kill_dups.cmd` hace `taskkill /PID 22632` fijo (frágil). El loop interno corre cada ~80 s con ciclos de 17–34 s.
- Logs: `backend/logs/bot.err.log` = 7 MB en 4 días (uvicorn manda todo a stderr; httpx loguea cada request a INFO). Sin rotación. 69 ERROR: "bot cycle failed", "could not resolve current phase", "could not record cycle failure", "could not mark source …" → errores intermitentes de BD (Neon) sin reintento.
- API local útil: `/api/bot/status`, `/api/bot/metrics`, `/api/bot/phase`, `/api/signals/decisions`, `/api/bot/pipeline`, `/api/bot/events`, `/simulation/accounts/1/summary`, `/api/learning/*` (requiere token).
- Spec 010 Learning: tasks.md sin casillas abiertas (revisar si realmente está cerrada).

## 3. Backtest de referencia (velas 1d Binance, 2017-08 → 2026-10-15)
Señal al cierre t, posición en t+1, coste 0.15%/cambio, solo largos, resto en USDT.

| BTCUSDT | CAGR | Max DD | Sharpe | Último año (oct-25→oct-26) |
|---|---|---|---|---|
| Buy & hold | 25.7% | 76.6% | 0.36 | −26% |
| **close > SMA50 y > SMA200** | **41.9%** | **45.7%** | **1.00** | **+18%, DD 6.9%** |

- Sensibilidad BTC (f∈{20,30,50,70,100} × s∈{100,150,200,250}): Sharpe 0.85–1.25 en todas → no hay parámetro mágico. ETH: 0.81–1.06.
- ETH 46%/año DD 44.7% (B&H 13%, DD 90%). SOL 79% DD 69%. BNB 70% DD 47%. **XRP y ADA: no funciona** (excluir).
- Cartera 50/50 BTC+ETH con la regla y rebalanceo mensual: CAGR 47%, DD 35%, Sharpe 1.19 desde 2018-03. Cuatro monedas (BTC/ETH/BNB/SOL) desde 2021: Sharpe 1.32.
- Por año BTC (regla vs B&H): 2018 −14/−68, 2022 0/−64 (protege en bajistas), 2020 +162/+302, 2024 +71/+121 (cede en alcistas).
- ~11 cambios de posición/año por activo vs 354 del ORB → costes ~3% vs ~106% del nominal anual.
- Riesgo de selección: se probaron 6 reglas estándar y se eligió esta; por eso la sensibilidad. Es backtest, no garantía.
- **Señal al cierre del 15-oct-2026:** BTC 82,246 > SMA50 81,258 > SMA200 72,324 → DENTRO (solo +1.2% sobre SMA50; un cierre < ~81k lo saca). ETH 2,442 < SMA50 2,555 → USDT. SOL 105.4 < 109.5 → USDT. BNB 729.7 < 744.6 → USDT.
- Datos: el VM/contenedor de la sesión no tenía red; se descargaron desde el navegador. En el repo, descargar 1d con `collect_klines.py` (verificar que acepte `--interval 1d` y `--days` ~3400).

## 4. Decisiones de dirección (propuestas, a ratificar por José en cada spec)
1. Apagar ORB (dejar el código en reposo, constitución #2). Archivar spec 012 como "no validada".
2. Núcleo = tendencia diaria (SMA50 & SMA200) en BTC+ETH, 50/50, USDT como refugio; BNB/SOL opcionales con más capital. Decisión una vez al día tras el cierre 00:00 UTC (20:00 Venezuela) con **lógica de recuperación** (si el PC estuvo apagado, evaluar la última vela cerrada al arrancar). Esto hace que "correr al iniciar sesión, varias veces al día" sea suficiente.
3. Sustituir "1 USD de riesgo por operación + stop 2%" (lógica de scalping) por **límites de asignación** por activo y breaker de drawdown de cartera. Esto toca la constitución #3 → requiere enmienda explícita aprobada por José.
4. Benchmark siempre contra buy & hold y DCA, no contra cero. Gate: Sharpe OOS > B&H y DD < B&H, y que el motor del bot reproduzca `backtest_tendencia_diaria.py` ±10%.
5. "Aprender" = revalidación walk-forward mensual + meseta de parámetros + Deflated Sharpe, registrando todas las variantes probadas (strategy_versions de spec 010). **El bot nunca se automodifica en vivo.**
6. Gemini = analista con veto que **solo reduce** exposición (JSON estructurado: sentimiento, eventos FOMC/CPI, veto + razón), y redactor del diario. A/B en paper núcleo vs núcleo+veto. Evidencia: LLMs operando solos pierden (Alpha Arena; preprint 2609.05663: reglas de riesgo en el prompt no cambian conducta, en el código sí).
7. Copytrading solo en **modo sombra** (endpoints públicos de OKX, seguidor virtual con fees 10–30% y slippage). Copy real implica futuros → prohibido por constitución #1 salvo enmienda.
8. Windows: Programador de tareas "Al iniciar sesión" con reintento → `iniciar_bot.bat`; scheduler dentro de la app (cada 4 h + decisión diaria); pidfile en vez de PID fijo; NSSM/WinSW si se quiere correr sin sesión; desactivar suspensión; sincronizar hora (recvWindow). Más adelante VPS para dinero real.
9. Logs: RotatingFileHandler (p. ej. 5×5 MB), httpx a WARNING, reintentos con backoff para Neon. Heartbeat (Telegram/correo).

## 5. Frontend: diagnóstico y dirección (paso 7 del plan)
Problemas vistos en las capturas: saldo repetido 5 veces con 8 decimales; números que se solapan con iconos a 1440 px; neón turquesa/cian/morado/naranja sin significado; tarjetas con borde izquierdo de color distinto cada una; mosaicos de iconos de colores; botón "+" flotante sin función; título gigante "Simulación"; la pantalla principal es un formulario de compra **manual** en un bot automático; gráfico BTC del sidebar plano; rail y sidebar se cortan a 900 px de alto; 22 nodos de pipeline casi todos DISABLED; en móvil, tarjetas repetidas antes de algo útil.
Dirección: "sala de control" sobria — neutros + un solo acento; verde/rojo solo para PnL; cifras tabulares, 2 decimales en USD; una sola cifra de equity con su curva **vs buy & hold**; tarjeta "Qué hará el bot hoy" (estado de la señal por par y distancia a la SMA); tarjeta de gates (backtest/paper/testnet); registro de decisiones en lenguaje natural; formulario manual a una pestaña secundaria; layout a altura completa. Prueba de éxito: alguien ajeno entiende en 10 s qué hace el bot y si va ganando. Hay skills de UI en `.opencode/skills/` (typeui-fundamentals, design-system, ui-ux-pro-max) y `design.json` (el diseño actual sale de ahí: es parte del problema, no la referencia a seguir).

## 6. Mercado (para calibrar, no para predecir)
BTC ATH ~126k (6-oct-2025); mínimo ~60.9k (7-jun-2026); ~81–82k el 15-oct-2026. Fed (Warsh) subió a 3.75–4.00% el 16-sep-2026; CPI sep 3.7%; 10Y ~5.37%. ETF BTC −540 M USD en octubre hasta el 14. F&G 41. Dominancia BTC 57–60% (no hay altseason). Próximos: FOMC 28-oct, midterms 3-nov. Postura: defensiva; dejar que la regla decida.

## 7. Advertencias
- Nada de esto es asesoría financiera; ninguna estrategia garantiza ganancias. La regla de tendencia tuvo DD histórico ~45% en BTC: el capital real debe ser el que José acepte ver caer eso.
- No tocar `ALLOW_LIVE_TRADING`. No poner claves ni `.env` en prompts. Claves de Binance sin permiso de retiro y con lista blanca de IP.
- Pedir confirmación antes de registrar tareas programadas, instalar servicios o cambiar la constitución.
