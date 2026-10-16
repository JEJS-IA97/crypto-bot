# Spec 013 — Núcleo de tendencia diaria (BTC + ETH, SMA50 & SMA200)

Estado: **borrador — pendiente de aprobación del propietario.** Bloqueada por la enmienda de la constitución #3 (ver D-6) y por los `[NEEDS DECISION]` marcados.
Depende de: 001 (loop, ejecutor de simulación, kill switch), 005 (eventos y decisiones auditables), 008 (motor de riesgo), 010 (`strategy_versions`), 011/012 (walk-forward, `walk_forward_runs`, gates de fase).
Fuentes: `docs/contexto-2026-10-16/README.md` §3–§4; `informe-estrategias-2026-10-16.md` (plan, pasos 2–3); `docs/contexto-2026-10-16/scripts/backtest_tendencia_diaria.py` (verdad de referencia); constitución #1–#13.

## Contexto

El ORB quedó en reposo (Paso 0a): v1 no pasó su walk-forward (PnL bruto negativo; ~354 cambios de posición al año cuestan ~106 % del nominal) y v2 nunca se evaluó. La investigación del 16-oct encontró una regla con evidencia: **estar comprado en un activo solo si su cierre diario está por encima de su SMA50 y de su SMA200; si no, quedarse en USDT.** En BTC (2017-08 → 2026-10), con un coste de 0,15 % por cambio: CAGR 41,9 %, DD máx. 45,7 % y Sharpe 1,00, frente al buy & hold (25,7 %, 76,6 % y 0,36). La regla protege en mercados bajistas (2018: −14 % frente a −68 %; 2022: 0 % frente a −64 %) y cede parte de las subidas en los alcistas. Hace unos 11 cambios al año por activo. En ETH también funciona. En XRP y ADA, no.

Esta spec convierte esa regla en el núcleo del bot, **en SIMULATION**. Antes de operar, el motor del propio bot tiene que reproducir el backtest de referencia. Al decidir una sola vez al día con recuperación, el bot tolera que el PC esté apagado: le basta con arrancar al iniciar sesión (Paso 0b).

## Decisiones de diseño

- **D-1 · Universo: BTCUSDT y ETHUSDT.** BNB y SOL quedan como opcionales, desactivados hasta que el capital supere ~100 USD. XRP y ADA quedan excluidos porque la regla no funciona en ellos.
- **D-2 · Señal.** Para cada activo, al cierre de la vela diaria `t` (Binance, 00:00 UTC): `IN` si `close_t > SMA50_t` **y** `close_t > SMA200_t`; en otro caso, `OUT`. Las medias son simples, se calculan sobre cierres diarios **cerrados** (nunca sobre la vela en curso) y en `Decimal`. Parámetros por defecto: fast = 50 y slow = 200, configurables y registrados en `strategy_versions`.
- **D-3 · Ejecución.** La posición objetivo que sale de la señal de `t` rige el día `t+1`. El bot decide **una vez por cada vela diaria cerrada**, en el primer ciclo posterior a las 00:00 UTC (20:00 en Venezuela). Si ese día ya decidió, no repite.
- **D-4 · Recuperación.** Al arrancar, o en cualquier ciclo, si la última vela diaria cerrada no tiene decisión registrada, el bot la evalúa en ese momento. Si se perdieron varios cierres (por ejemplo, el PC estuvo apagado varios días), **solo se evalúa el último cierre**: no se reconstruyen operaciones pasadas.
- **D-5 · Asignación.** El capital aportado (40 USD) se reparte **50 / 50** entre BTC y ETH. Cada activo tiene su "cubeta": `IN` ⇒ la cubeta está comprada en el activo; `OUT` ⇒ la cubeta queda en USDT. Una cubeta en `OUT` no se presta a la otra.
  - Rebalanceo mensual de las cubetas `IN` hacia el 50 %: `[NEEDS DECISION]`. Con 40 USD, los ajustes suelen quedar por debajo del mínimo de Binance (5 USD). Propuesta: rebalancear solo si la desviación supera el 10 % **y** la orden resultante cumple `min_notional`; si no, no se toca.
- **D-6 · Riesgo por asignación, no por operación.** La regla actual (constitución #3: riesgo ≤ 1 USD por operación con un stop del 2 %) es de scalping y no encaja: el núcleo no usa SL/TP fijos, y una cubeta de 20 USD puede caer más de 1 USD. Sustitución propuesta:
  - un tope de asignación por activo (≤ 50 % del capital aportado);
  - mantener la pérdida diaria ≤ 5 %, que bloquea compras nuevas ese día UTC;
  - un breaker de drawdown de cartera.
  - **Esto exige enmendar la constitución #3. `[NEEDS DECISION]`: ¿apruebas la enmienda?** Hasta entonces, esta spec no puede implementarse.
  - Umbral del breaker de drawdown de cartera: `[NEEDS DECISION]`. El DD histórico de la regla es ~45 % en BTC y ~35 % en la cartera 50 / 50. Un umbral más bajo cambia la estrategia que se validó. Opciones: (a) 35 %, que pasa a todo USDT y exige reinicio manual; (b) sin breaker de cartera, solo con la pérdida diaria y el kill switch.
- **D-7 · Posiciones sin SL/TP fijo.** Las posiciones que abre el núcleo solo se cierran por una señal `OUT`, por el kill switch o por el breaker de cartera. Los cierres por stop/take-profit del 2 % (spec 001, RF-13) **no se aplican** a ellas. El límite de "segunda posición correlacionada" del motor de riesgo (spec 008) tampoco se aplica entre las dos cubetas del núcleo, porque la correlación ya está asumida en la asignación 50 / 50.
- **D-8 · Convivencia.** El núcleo es la única estrategia técnica activa. Las señales externas (spec 001, RF-8) siguen como hoy. El ORB sigue en reposo (`orb_enabled=False`).
- **D-9 · Datos.** Se usan velas 1d de Binance Spot. Para el loop, se piden por API en cada decisión: bastan ≥ 201 velas cerradas. Para backtest y walk-forward, se leen de `data/klines_1d/<SYMBOL>.jsonl`, descargado con `collect_klines.py --interval 1d`, que ya está soportado. El rango completo es desde 2017-08.
- **D-10 · Validación contra la referencia.** El motor del bot, en modo backtest, debe reproducir `backtest_tendencia_diaria.py` con un margen de ±10 % en CAGR, DD máx. y Sharpe, usando el mismo dataset y el mismo coste (0,15 % por cambio). Como la referencia usa `float` y el bot usa `Decimal`, solo se comparan las métricas, nunca centavo a centavo.
- **D-11 · Evaluación y gate (sustituye el gate de spec 012 para esta estrategia).** Se usan ventanas de 12 meses fuera de muestra. La regla no se optimiza: los parámetros son fijos, así que cada ventana es directamente fuera de muestra. Además se calcula una **meseta de sensibilidad** con f ∈ {20, 30, 50, 70, 100} × s ∈ {100, 150, 200, 250}. Veredicto **PASA** ⇔ se cumplen las cuatro condiciones:
  1. el Sharpe de la cartera > el Sharpe del buy & hold;
  2. el DD máx. de la cartera < el DD máx. del buy & hold;
  3. la reproducción de la referencia está dentro de ±10 % (D-10);
  4. la meseta no muestra un parámetro "mágico": `[NEEDS DECISION]`. Propuesta: el Sharpe de todas las combinaciones f × s ≥ 0,7.
  - El benchmark se informa siempre frente al buy & hold y frente a un DCA mensual, nunca frente a cero.
- **D-12 · Gates de fase.**
  - SIMULATION→TESTNET exige que la última corrida **de esta estrategia** sea PASA. Hoy el gate lee la última corrida sin distinguir estrategia, así que una corrida del ORB podría decidirlo.
  - TESTNET→LIVE exige hoy ≥ 30 trades en paper. Con ~22 cambios al año, eso tardaría más de un año. `[NEEDS DECISION]`. Propuesta (paso 3 del plan): ≥ 3 meses de paper, desviación de ejecución frente a la simulación teórica < 0,3 % por operación y cero órdenes rechazadas por filtros.
- **D-13 · Auditable y visible.** Cada decisión diaria se persiste aunque no haya orden. Guarda: el activo, la vela usada, el cierre, SMA50, SMA200, la señal, la posición objetivo, la acción (comprar / vender / mantener / no operable) y el motivo. Un endpoint de solo lectura expone "qué hará el bot hoy" para el panel (paso 7 del plan).

## Requisitos funcionales

**RF-1 · Cálculo de la señal** *(Ubicuo)*. El sistema SHALL calcular, para cada activo del universo, `close`, `SMA_fast` y `SMA_slow` sobre velas diarias cerradas, en `Decimal`, y SHALL emitir `IN` si `close > SMA_fast` y `close > SMA_slow`, y `OUT` en otro caso (D-2). El cálculo SHALL ser una función pura del dominio, sin red ni BD.

**RF-2 · Datos insuficientes** *(Unwanted)*. SI hay menos de `slow + 1` velas diarias cerradas, o la última vela no es la del día UTC anterior, ENTONCES el sistema SHALL registrar la decisión como "no operable" con su motivo y SHALL NOT abrir posiciones nuevas en ese activo (fail-closed). Las posiciones abiertas se mantienen.

**RF-3 · Una decisión por cierre** *(Event-driven)*. CUANDO un ciclo del loop corre después de un cierre diario que aún no tiene decisión registrada para un activo, el sistema SHALL evaluar ese cierre y registrar exactamente una decisión por activo y por vela diaria (D-3). Los ciclos siguientes del mismo día SHALL NOT volver a decidir.

**RF-4 · Recuperación tras apagado** *(Event-driven)*. CUANDO el bot arranca y la última vela diaria cerrada no tiene decisión, el sistema SHALL evaluarla en el primer ciclo. Si faltan varios cierres, SHALL evaluar solo el último y registrar en el motivo cuántos cierres se omitieron (D-4).

**RF-5 · Transiciones de posición** *(Event-driven)*. CUANDO la señal de un activo pasa a `IN` y su cubeta está en USDT, el sistema SHALL comprar por el valor de la cubeta, respetando `min_notional` y `step_size`. CUANDO pasa a `OUT` con la cubeta comprada, SHALL vender toda la posición. CUANDO la señal no cambia, SHALL NOT operar (salvo el rebalanceo de D-5, si se aprueba).

**RF-6 · Asignación y límites** *(Ubicuo)*. El valor comprado en cada activo SHALL ser ≤ 50 % del capital aportado configurado, y la suma SHALL ser ≤ 100 %. Si una orden no cumple los filtros del exchange, SHALL rechazarse y registrarse sin reintentar a un tamaño distinto.

**RF-7 · Sin SL/TP fijo y sin bloqueo por correlación** *(Ubicuo)*. Las posiciones del núcleo SHALL NOT cerrarse por los stops o take-profits porcentuales de la spec 001, y SHALL NOT bloquearse por el límite de segunda posición correlacionada de la spec 008 entre BTC y ETH (D-7). El resto de controles de riesgo (pérdida diaria, kill switch, breaker de ciclos, `ALLOW_LIVE_TRADING`) siguen aplicándose.

**RF-8 · Breaker de cartera** *(State-driven)*. MIENTRAS el drawdown de la cartera desde su máximo supere el umbral aprobado (D-6, `[NEEDS DECISION]`), el sistema SHALL NOT abrir posiciones nuevas, SHALL pasar las cubetas a USDT y SHALL exigir un reinicio manual para reanudar.

**RF-9 · Decisión auditable** *(Ubicuo)*. Cada decisión diaria SHALL persistir los campos de D-13, más la versión de estrategia y el `correlation_id` del ciclo (constitución #10), aunque la acción sea "mantener".

**RF-10 · Estado de la señal (API)** *(Event-driven)*. CUANDO se consulta el endpoint de estado del núcleo, el sistema SHALL devolver, por activo: la señal vigente, el cierre, SMA50, SMA200, la distancia porcentual del cierre a cada media, la posición objetivo, la fecha de la próxima decisión y la última acción. Es de solo lectura y sin token, como `/api/bot/status`.

**RF-11 · Backtest con el motor del bot** *(Event-driven)*. CUANDO se ejecuta el backtest offline sobre `data/klines_1d`, el sistema SHALL usar la misma función de señal de RF-1. Con la señal de `t`, SHALL aplicar la posición en `t+1` y un coste configurable por cambio (por defecto, 0,15 %). SHALL reportar CAGR, retorno total, DD máx., Sharpe (retornos diarios × √365), número de cambios y exposición, por activo y para la cartera 50 / 50.

**RF-12 · Reproducción de la referencia** *(Ubicuo)*. Sobre el mismo dataset, las métricas de RF-11 SHALL quedar dentro de ±10 % de las de `backtest_tendencia_diaria.py` (D-10).

**RF-13 · Evaluación, sensibilidad y benchmark** *(Event-driven)*. CUANDO se ejecuta la corrida de evaluación, el sistema SHALL producir un reporte Markdown en español con:
- las métricas por ventana de 12 meses;
- la meseta f × s;
- la comparación frente al buy & hold y frente a un DCA mensual;
- el veredicto PASA / NO PASA según D-11.

Además, SHALL persistir la corrida identificando la estrategia.

**RF-14 · Gate de fase por estrategia** *(Event-driven)*. CUANDO se solicita SIMULATION→TESTNET con el núcleo activo, el sistema SHALL exigir que la última corrida **de esta estrategia** sea PASA. Las corridas del ORB SHALL NOT contar.

**RF-15 · Sin look-ahead** *(Unwanted)*. SI una decisión o un backtest usara datos de la vela `t+1` o posteriores para decidir `t`, el sistema estaría en error. Los tests SHALL incluir un caso que lo delate.

**RF-16 · Simulación por defecto** *(Ubicuo)*. Todo lo anterior SHALL operar en SIMULATION. Ninguna orden real SHALL enviarse sin `ALLOW_LIVE_TRADING=true` y fase LIVE (constitución #4–#5).

## Requisitos no funcionales

- Python 3.14, sin dependencias nuevas (constitución #12). Dinero y precios en `Decimal` (constitución #11).
- La decisión diaria cabe en un ciclo normal del loop: dos llamadas de klines 1d por activo como máximo.
- Idioma: reporte, mensajes y endpoint en español; código en inglés (constitución #13).

## Casos límite

1. El PC estuvo apagado 3 días: al arrancar se evalúa solo el último cierre; el motivo registra "2 cierres omitidos" (RF-4).
2. El bot arranca a las 23:59 UTC y sigue corriendo a las 00:01: decide en el primer ciclo posterior al cierre (RF-3).
3. El cierre queda exactamente igual a una SMA: cuenta como `OUT`, porque la condición es estrictamente mayor (RF-1).
4. Binance devuelve la vela del día en curso: se descarta y solo se usan velas cerradas (RF-1, RF-15).
5. La cubeta vale menos que `min_notional` (por ejemplo, tras pérdidas): la compra se rechaza y se registra; el activo queda en USDT (RF-6).
6. El kill switch está activo al cierre: la decisión se registra como "bloqueada por kill switch" y no hay orden (RF-9).
7. Hay una posición abierta de antes (ORB o externa) en BTC cuando el núcleo pide `IN`: `[NEEDS DECISION]`. Propuesta: el núcleo adopta la posición como su cubeta si su valor ≤ 50 %; si no, registra un conflicto y no opera ese activo.
8. Una señal externa contradice la del núcleo en el mismo ciclo: gana la externa, como en la spec 001 (RF-8 de 001), y queda registrada.

## Fuera de alcance

- BNB y SOL (D-1); se activan en una spec posterior cuando haya más capital.
- El veto de Gemini (paso 5), el copytrading en modo sombra (paso 6) y el bucle mensual de aprendizaje con Deflated Sharpe (paso 4).
- El rediseño del frontend (paso 7). Aquí solo entra el endpoint de RF-10.
- Órdenes limit y comisión en BNB: solo afectan a LIVE (paso 8).
- Heartbeat por Telegram y scheduler APScheduler. El loop actual, con la lógica de "una vez por cierre", basta.
- Borrar el código del ORB (constitución #2).

## Mapeo RF → tests (propuesto; se cierra en el plan)

| RF | Tests |
|----|----|
| RF-1, RF-2, RF-15 | `tests/test_trend_signal.py` (función pura, medias, empates, datos insuficientes, vela en curso descartada) |
| RF-3, RF-4, RF-5, RF-6, RF-7, RF-9 | `tests/test_trend_loop.py` (loop con mercado falso: una decisión por cierre, recuperación, transiciones, filtros, sin SL/TP) |
| RF-8 | `tests/test_trend_loop.py` (umbral de DD de cartera) |
| RF-10 | `tests/test_trend_api.py` |
| RF-11, RF-12, RF-13 | `tests/test_trend_backtest.py` (fixture 1d; comparación con la referencia en fixture sintético) |
| RF-14 | `tests/test_phase_service.py` (gate por estrategia) |
| RF-16 | aserciones en `tests/test_trend_loop.py` (solo `SimulationExecutor`) |

## Criterios de finalización

1. Los 16 RF implementados, cada uno con su test en verde, y la suite completa en verde, con ruff limpio.
2. Una corrida real sobre `data/klines_1d` (BTC y ETH, desde 2017-08) reproduce la referencia dentro de ±10 % y produce un reporte con veredicto.
3. El veredicto es PASA según D-11; si es NO PASA, el núcleo no se activa en el loop y se informa al propietario.
4. En SIMULATION, el bot registra la decisión diaria de BTC y ETH al menos 3 días seguidos, incluido un arranque tras un apagado (recuperación).
5. La constitución #3 está enmendada con la aprobación explícita del propietario antes de la primera tarea de implementación.
6. `tasks.md` tiene todas sus casillas marcadas.
