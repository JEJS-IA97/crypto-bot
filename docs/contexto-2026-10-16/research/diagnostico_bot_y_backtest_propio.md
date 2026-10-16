# Diagnóstico del bot crypto-bot del usuario + backtest propio (2026-10-16)

Fuente: lectura directa del repo en la PC del usuario (C:\...\projects\crypto-bot), su API local (127.0.0.1:8000) y velas diarias públicas de Binance descargadas hoy. Hecho por el coordinador, no por un investigador web.

## 1. Qué es el bot hoy (verificado en código)
- Backend Python 3.14 + FastAPI + SQLAlchemy, BD Postgres en Neon; frontend React 19 + Vite. ~13k líneas, ~90 archivos de tests (unittest). Método SDD con specs 001–012 y una constitución de 13 reglas (Binance Spot only, Decimal, kill switch, fases SIMULATION→TESTNET→LIVE, ALLOW_LIVE_TRADING).
- Estrategia activa: ORB (Opening Range Breakout) 9:00–9:30 NY como rango, ruptura 9:30–10:00 NY, velas 5m, solo largos, SL/TP 2% (TAKE_PROFIT = STOP_LOSS, RR 1:1), pares BTC/ETH/BNB/SOL/ADA. Spec 012 añadió filtro "cierre ≥ EMA50 de velas 1h". Versión en logs: orb-001-v3.
- Antes usaba un motor EMA20/50 + RSI + volumen en velas 15m (decisiones del 6-oct).
- Riesgo: 1 USD máx por operación, pérdida diaria 5%, 3 posiciones, exposición ≤75%, circuit breaker, kill switch. Capital configurado 40 USD (paper).
- IA: Gemini como analista bajo demanda (≤4 consultas/día), solo recomienda. Estado real hoy: fuente "gemini" DISABLED, 0 consultas en 24 h. Learning (spec 010): hipótesis con activación manual, endpoints protegidos por token.
- Fuentes de datos: solo klines y exchangeInfo de Binance funcionan; order book, noticias, fear&greed, sentimiento, derivados, regime detector: deshabilitados o stubs (el panel los muestra como nodos DISABLED).
- Copy trading: no existe (solo webhook de señales externas con TTL).
- Arranque: iniciar_bot.bat lanza uvicorn oculto en 127.0.0.1:8000; el loop interno corre cada ~80 s (ciclos de 17–34 s de latencia). No hay tarea programada de Windows registrada en el repo para el inicio de sesión (el .bat es manual). Hay un .cmd que hace `taskkill /PID 22632` fijo (frágil).
- Logs: bot.err.log de 7 MB en 4 días (uvicorn escribe todo a stderr; cada request httpx se loguea a INFO) → crecerá sin rotación. 69 líneas ERROR: "bot cycle failed", "could not resolve current phase", "could not mark source …" (errores intermitentes de BD/Neon).

## 2. Evidencia de rendimiento del bot
- Walk-forward ORB v1 (reports/walk-forward-20261010…md): 6 folds 2025-10→2026-10, 5 pares, 5m, comisión 0.1%/lado + slippage 0.05%/lado, capital 20 USD: PnL neto −16.96 USD (−14.1%), 0/6 folds positivos, 354 trades, 54 ganadores (15%), profit factor 0.24, Sharpe −7.1, comisiones 14.16 USD. Buy & hold en el mismo periodo: BNB +5.65, BTC +4.07, ETH +4.33, SOL +8.42, ADA −0.30 USD sobre 20 USD. Veredicto propio del bot: NO PASA.
- PnL bruto antes de costes ≈ −2.8 USD → la señal no tenía ventaja ni antes de comisiones.
- Spec 012 (ORB v2 + filtro EMA50 1h): T10 (correr walk-forward v2 con datos reales) NO hecho → la estrategia que corre en paper desde el 12-oct nunca pasó su propio gate.
- Paper real (API local hoy): balance 39.80 USD de 40 → PnL realizado −0.29 USD, drawdown 0.73%, 5 operaciones cerradas en 10 días: 4 perdedoras, 1 ganadora (+0.005). Una orden rechazada por "stale_fill_missing_schema_drift" (bug de esquema ya parcheado en commit 436f284).
- Fase: SIMULATION. live_blockers activos. Correcto.

## 3. Backtest propio de reglas de tendencia diarias (velas 1d Binance, 2017-08→2026-10-15)
Método: señal al cierre del día t, posición desde el día t+1 (sin look-ahead); coste 0.15% por cambio de posición (0.10% comisión + 0.05% slippage); solo largos, el resto en USDT (sin interés). Sharpe anualizado sobre retornos diarios (√365). "1Y" = 15-oct-2025→15-oct-2026. Advertencia: probé 6 reglas estándar (riesgo de selección); por eso se añadió análisis de sensibilidad.

BTCUSDT
| Regla | CAGR total | Max DD total | Sharpe total | Últimos 3 años | Último año |
|---|---|---|---|---|---|
| Buy & hold | 25.7% | 76.6% | 0.36 | 44.6%/año, DD 53% | −26%, DD 48.8% |
| Precio > SMA200 | 26.3% | 64.4% | 0.57 | 37.6%, DD 32% | +7%, DD 9.9% |
| Precio > SMA50 y > SMA200 | 41.9% | 45.7% | 1.00 | 42.8%, DD 24.6%, Sh 1.21 | +18%, DD 6.9% |
| SMA10 > SMA40 | 36.2% | 55% | 0.76 | 37.6% | 0% |
| Donchian 20/10 | 35.1% | 54.2% | 0.79 | 21.5% | −6% |
| Momentum 28d revisado cada 5d | 30.3% | 63.4% | 0.66 | 27.2% | −17% |

ETH: B&H 13%/año DD 90%; SMA50&200 46%/año DD 44.7% Sh 0.82; último año B&H −39% vs regla +10% (DD 11%).
SOL (desde 2020): B&H 44.6% DD 96%; SMA50&200 79% DD 69% Sh 0.92; último año B&H −46% vs +23%.
BNB: B&H 61.5% DD 76%; SMA50&200 70% DD 47% Sh 0.99; último año −37% vs +3%.
XRP y ADA: reglas de tendencia flojas o negativas en algunos periodos (XRP SMA200 −4.5%/año total). Conclusión: aplicar solo a los grandes y líquidos.

Sensibilidad BTC regla "precio > SMA_f y > SMA_s" (Sharpe total): todas las combinaciones f∈{20,30,50,70,100}, s∈{100,150,200,250} dan Sharpe 0.85–1.25 y DD 37–66%, contra 0.36 / 77% del B&H → la ventaja no depende de un parámetro mágico. ETH: Sharpe 0.81–1.06.

BTC por año (regla SMA50&200 vs B&H): 2018 −14% vs −68%; 2019 +61% vs +94%; 2020 +162% vs +302%; 2021 +49% vs +60%; 2022 0% vs −64%; 2023 +92% vs +156%; 2024 +71% vs +121%; 2025 −3% vs −6%; 2026 (a 15-oct) +18% vs −6%. Patrón: gana poco en alcistas fuertes, evita casi todo el daño en bajistas.

Cartera 50/50 BTC+ETH, cada mitad con la regla SMA50&200, rebalanceo mensual: desde 2018-03 CAGR 47% DD 35% Sharpe 1.19 (×27.6 vs B&H ×5.0); último año +14% DD 8.3% (B&H ×0.68).
Cartera 25% BTC/ETH/BNB/SOL con la regla: desde 2021-02 CAGR 50% DD 36.6% Sharpe 1.32 (×9.8 vs B&H ×3.7); 3 años Sharpe 1.38; último año +13.5% DD 9.3% (B&H ×0.63).
Número de cambios de posición: ~100 en 9 años en BTC (≈11/año) vs 354 en un año del ORB.

Estado de la señal hoy (cierre 15-oct-2026): BTC 82,246 > SMA50 81,258 y > SMA200 72,324 → DENTRO (por poco: 1.2% sobre la SMA50). ETH 2,442 < SMA50 2,555 → CASH. SOL 105.4 < SMA50 109.5 → CASH. BNB 729.7 < SMA50 744.6 → CASH. XRP → CASH. ADA → dentro (pero regla poco fiable en ADA). BTC está 34% bajo su máximo diario de cierre (124,659), ETH 49%, SOL 60%.

## 4. Frontend (capturas reales del panel con datos de la API)
Problemas que lo hacen ver "hecho por IA":
- Mismo saldo repetido 5 veces en una pantalla (tarjeta "Cuenta activa", fila de stats, tarjeta Capital, sidebar Balance total, Estado→Saldo), con 8 decimales ($39.79824426). Números se solapan con iconos (Disponible/Invertido, PnL realizado/no realizado) a 1440 px.
- Paleta neón turquesa/cian/morado/naranja asignada sin significado; tarjetas con borde izquierdo de color distinto cada una; mosaicos de iconos de colores; botón "+" flotante sin función clara; título gigante "Simulación".
- Para un bot automático, la pantalla principal es un formulario de compra manual ("Ejecutar operación"), y lo importante (¿qué estrategia corre?, ¿pasó su backtest?, ¿qué hará hoy?, PnL vs buy&hold) no aparece.
- El gráfico de BTC del sidebar está vacío/plano; precios con 0.00% de cambio; la columna izquierda y derecha se cortan a 900 px de alto (no se estiran con la página).
- Pipeline con 22 nodos, la mayoría DISABLED → ruido.
- En móvil: lista larga de tarjetas repetidas antes de llegar a algo útil.
Dirección propuesta: panel de "sala de control" sobrio (neutros, un solo color de acento, verde/rojo solo para PnL), tipografía tabular para cifras, 2 decimales en USD, una sola cifra de equity con su curva vs buy&hold, tarjeta "Qué hará el bot hoy" (estado de la señal por par), tarjeta de gates (backtest/paper/testnet), registro de decisiones legible en lenguaje natural, y mover el formulario manual a una pestaña secundaria.
