# Spec 011 — Evidencia: backtest walk-forward de ORB con métricas y gate

Estado: implementada (T1-T5 completadas; aprobada por el propietario el 2026-10-10)
Depende de: 001 (ORB operando en paper, `collect_klines.py` y `strategy_lab_service.backtest_orb/grid_search_orb`), 009 (sistema de diseño y disciplina de specs previas).
Fuentes: plan-maestro §6 Fase B; constitución #9 (backtest train/valid/test sin look-ahead, sin métrica ⇒ no entra), #11 (Decimal, núcleo testeable sin red), #12 (sin dependencias nuevas); código existente `backend/app/services/strategy_lab_service.py` (RF-15/RF-27 de 001).

## Contexto

La Fase B exige que "ORB tenga un veredicto con datos fuera de muestras" antes de avanzar hacia dinero real: *"si ninguna estrategia supera comisiones fuera de muestra, no se avanza"*. Hoy existe backtest puntual (`backtest_orb`, split único `split_candles`, grid de parámetros) y un recolector de klines reanudable, pero **no** hay ventanas rodantes, ni métricas de riesgo/expectativa completas, ni reporte de evidencia, ni gate explícito. Esta spec construye el pipeline de evidencia reproducible sobre ORB (única estrategia en alcance, D-1 de Fase D más adelante). Es una corrida offline: no toca el bot, la BD ni la API.

## Decisiones de diseño

- **D-1 · Alcance: solo ORB.** El walk-forward evalúa exclusivamente `backtest_orb` (la estrategia que opera el bot). El backtest genérico de velas y estrategias nuevas quedan para specs futuras (Fase D).
- **D-2 · Dataset: los JSONL del recolector existente.** Se consumen los ficheros `data/klines/<SYMBOL>.jsonl` que produce `backend/collect_klines.py` (Decimal como texto, reanudable). **Intervalo 5m**, porque `backtest_orb` requiere las 6 velas 9:00–9:30 AM NY (a 15m solo caben 2); se invocará `collect_klines.py --interval 5m` — **ratificado por el propietario** en la clarificación. Símbolos por defecto: los 4 pares con señal ORB (`orb_symbols` de `config.py`: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT); la CLI admite cualquier par de los 8 recolectados. La recolección es **prerequisito de la Fase A pendiente**, no parte de esta spec. Nada de red dentro de la spec (constitución #11).
- **D-3 · Folds rodantes con validación interna (ratificado).** Un fold = train `[t, t+180d)` + test `[t+180d, t+210d)`; el siguiente fold arranca en `t+30d` (train se solapa entre folds, **test nunca entra en train de ningún fold**, sin look-ahead). Dentro de cada ventana de train, el **último ~15 % se usa como validación** para elegir el mejor candidato del grid (reutilizando `split_candles`), cumpliendo la constitución #9 (train/valid/test). Defaults 180/30/30 d, configurables. Valores del grid: `stop_loss_pct` × `take_profit_pct` (lista de valores cerrada en el plan; los timings ORB quedan en sus defaults); reutilizar `grid_search_orb` si encaja.
- **D-4 · Costes explícitos y configurables.** Comisión `0.10 %` por lado + slippage `0.05 %` por lado (defaults editables), aplicados en Decimal dentro del test; la lógica de entradas/salidas de `backtest_orb` no se modifica. **Candidatos del grid cuya pérdida máxima (SL) a 20 USD supere 1 USD se descartan antes de evaluar** (constitución #3, ratificado).
- **D-5 · Cinco métricas obligatorias.** Retorno neto, máximo drawdown, Sharpe, profit factor y expectancy — todo Decimal, fórmulas fijas en el plan. Sharpe: media ÷ desviación **poblacional** de los retornos diarios de equity dentro de la ventana de test, anualizada × √252, sin tasa libre de riesgo; si hay menos de 2 días con equity o la desviación es 0 ⇒ Sharpe = 0.
- **D-6 · Salida: CLI + reporte Markdown.** Comando offline que escribe `reports/walk-forward-<timestamp>.md` en español: parámetros de la corrida, tabla por ventana, agregado out-of-sample, comparativa informativa vs buy & hold y veredicto explícito **PASA / NO PASA**. Sin tablas nuevas ni endpoints.
- **D-7 · Gate de Fase B.** `PASA` ⇔ **suma aritmética** de los PnL netos de test > 0 en el agregado out-of-sample (cada ventana test arranca con **20 USD aislados**, sin equity continuo — ratificado). La comparativa vs buy & hold se reporta como referencia, **no** forma parte del gate.
- **D-8 · Fail-closed en datos.** Si falta algún símbolo pedido, si el dataset está vacío/corrupto o si no alcanza train+test para un fold, la corrida no arranca: error claro (nunca inventar datos). Validación mínima de velas: `open_time` estrictamente creciente, precios parseables como `Decimal`, `low ≤ min(open, close) ≤ max(open, close) ≤ high`.
- **D-9 · Sin integración con Learning en este spec.** El reporte es evidencia para el propietario; enlazarlo con `strategy_versions` (Fase F / spec 015) queda fuera de alcance.
- **D-10 · Aprobación de la spec con fixtures (ratificado).** El gate de cierre de esta spec se demuestra con dataset fixture en tests y una corrida demo; un reporte con dataset real queda como paso posterior de Fase A y **no bloquea** el cierre.

## Requisitos funcionales

**RF-1 · Dataset de entrada** *(Ubicuo)*. El sistema SHALL consumir klines históricos SOLO desde `data/klines/<SYMBOL>.jsonl` (formato del recolector existente, velas ordenadas y Decimal como texto), sin red, validando cada vela según D-8. Intervalo 5m; símbolos por defecto los 4 pares ORB de `config.py` (D-2), ampliables por CLI.

**RF-2 · Ventanas rodantes sin look-ahead** *(Event-driven)*. CUANDO se ejecuta una corrida, el sistema SHALL partir la serie en folds consecutivos con la construcción exacta de D-3 (train `[t, t+180d)`, test `[t+180d, t+210d)`, siguiente `t += 30d`), garantizando que ninguna vela de test participa en el train de su fold ni de ningún otro; en cada fold SHALL optimizar `stop_loss_pct` × `take_profit_pct` (grid cerrado del plan, candidatos que violen 1 USD de pérdida máxima descartados, D-4) usando el train con validación interna del último ~15 % (D-3), y evaluar el test SOLO con los parámetros ganadores.

**RF-3 · Costes en cada trade de test** *(Ubicuo)*. Cada trade evaluado en ventanas de test SHALL aplicar comisión y slippage configurables (default 0.10 % / 0.05 % por lado) en `Decimal`; el motor de entradas/salidas ORB existente SHALL usarse sin modificar su lógica de señales.

**RF-4 · Métricas por ventana y agregado** *(Ubicuo)*. Para cada ventana de test y para el agregado out-of-sample, el sistema SHALL calcular en `Decimal`: retorno neto (% sobre los 20 USD aislados de la ventana), máximo drawdown, Sharpe (según D-5), profit factor (pérdidas 0 ⇒ `n/a` con nota, nunca infinidad) y expectancy (p medio por trade). Mismo dataset ⇒ mismos valores.

**RF-5 · Reporte Markdown de evidencia** *(Event-driven)*. CUANDO la corrida termina, el sistema SHALL escribir `reports/walk-forward-<timestamp>.md` (español) con: dataset y periodo, símbolos, costes, parámetros de folds, tabla de métricas por fold, agregado out-of-sample (suma aritmética de PnL de test, D-7), comparativa vs buy & hold — misma ventana temporal `[primer test start, último test end]`, mismo capital 20 USD, entrada al close del primer candle y salida al close del último, en USD absolutos, marcando los huecos entre tests si los hay (informativa) — y el veredicto PASA/NO PASA.

**RF-6 · Gate PASA/NO PASA** *(Event-driven)*. CUANDO se emite el veredicto, PASA SHALL significar exactamente: PnL neto total agregado out-of-sample > 0 tras costes; en caso contrario NO PASA. El veredicto SHALL ser determinista (corrida idéntica ⇒ veredicto idéntico).

**RF-7 · CLI offline** *(Event-driven)*. CUANDO el propietario invoca el comando de corrida (p. ej. `python run_walk_forward.py --symbols ... --days ... --train-days ... --test-days ... --step-days ...`), el sistema SHALL ejecutar la corrida completa y reportar el veredicto en consola y en el reporte; código de salida 0 = corrida completada, distinto de 0 = error de entrada/dataset (el veredicto NO PASA no es error).

**RF-8 · Aislamiento total** *(Unwanted)*. SI una corrida se ejecuta en tests, SHALL usar fixtures JSONL temporales en disco temporal, SIN red, SIN tocar la base de datos, `bot_loop`, riesgo ni ejecución; ningún servicio de esta spec SHALL importar máquinas de trading en ejecución (patrón `test_ai_isolation`).

**RF-9 · Determinismo y Decimal** *(Ubicuo)*. Mismo dataset y mismos parámetros de corrida ⇒ mismas métricas y mismo veredicto; TODOS los cálculos (precios, PnL, métricas) en `Decimal` (constitución #11), sin `float`.

## Requisitos no funcionales

- Python 3.14; stdlib + dependencias ya declaradas en `requirements.txt` (sin dependencias nuevas, constitución #12).
- Corrida offline desde `backend/`; el reporte en Markdown legible por el propietario sin herramientas extra.
- Idioma: reporte y mensajes en español; código e identificadores en inglés (constitución #13).
- Rendimiento razonable: 365 d × 8 símbolos a 5m (~84 000 velas/símbolo) no debe exigir memoria desmedida; procesar por símbolo.

## Casos límite

1. Falta `data/klines/` o algún símbolo pedido ⇒ error claro, corrida no arranca (D-8).
2. Dataset menor que train+test ⇒ error "dataset insuficiente para una ventana" (D-8).
3. Ventana de train sin trades ⇒ se usan los parámetros por defecto y la ventana se marca "sin trades en train" en el reporte (no aborta).
4. Ventana de test sin trades ⇒ PnL 0 de la ventana; el agregado sigue calculándose.
5. Pérdidas totales 0 ⇒ profit factor `n/a` con nota (RF-4).
6. Sharpe con varianza 0 o con menos de 2 días de equity en la ventana ⇒ 0 (D-5).
7. Velas con timestamps no crecientes, precios no parseables como `Decimal` o OHLC inconsistente (`low > min(open, close)` o `high < max(open, close)`) ⇒ error de formato, corrida no arranca (D-8).
8. Buy & hold se calcula sobre el rango `[primer test start, último test end]` del agregado (misma referencia temporal, sin cherry-picking); si hay huecos entre tests se marcan como nota en el reporte (RF-5).
9. Todas las ventanas de test sin trades ⇒ agregado 0 ⇒ veredicto NO PASA, corrida válida y completada (no es error, RF-7).

## Fuera de alcance

- Recolectar klines (Fase A, `collect_klines.py`, prerequisito D-2).
- Estrategias distintas de ORB (Fase D, spec 013).
- Persistencia en tabla/BD, endpoint API o UI del reporte (D-6: solo CLI + fichero).
- Enlace con `strategy_versions`/Learning (D-9, Fase F).
- Paper-trading, testnet o dinero real: el gate de esta spec es evidencia, no autoriza nada por sí solo (constitución #4/#5).
- Walk-forward de portafolios o múltiples estrategias (Fase D).

## Mapeo RF → tests

| RF | Tests (backend: `cd backend; .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`) |
|----|----|
| RF-1 | `tests/test_walk_forward.py` (carga de fixtures JSONL, errores fail-closed) |
| RF-2 | `tests/test_walk_forward.py` (ventanas, solapes, sin look-ahead, configuración) |
| RF-3 | `tests/test_wf_metrics.py` (comisión/slippage aplicados en Decimal) |
| RF-4 | `tests/test_wf_metrics.py` (5 métricas, casos límite 5/6) |
| RF-5 | `tests/test_walk_forward_cli.py` (estructura del Markdown, veredicto presente) |
| RF-6 | `tests/test_walk_forward_cli.py` (PASA ⇔ agregado > 0) |
| RF-7 | `tests/test_walk_forward_cli.py` (códigos de salida) |
| RF-8 | `tests/test_walk_forward_isolation.py` (sin red, sin imports prohibidos) |
| RF-9 | aserciones en `tests/test_walk_forward.py` y `tests/test_wf_metrics.py` (misma corrida ⇒ mismos números; sin float) |

## Criterios de finalización

1. Los 9 RF implementados y verificados con su test en verde.
2. Ventanas rodantes probadas: sin look-ahead comprobado con fixture que lo delataría (un pico de test que cambiaría train).
3. Las 5 métricas probadas contra valores calculados a mano en un dataset minúsculo.
4. Una corrida demo end-to-end con **fixtures temporales** genera un reporte completo con veredicto PASA/NO PASA explícito (criterio de aprobación, D-10); el reporte con dataset real queda para Fase A y no bloquea.
5. Suite backend completa en verde + ruff + compileall (y `npm run lint`/`npm test` intactos por RF-9).
6. `tasks.md` con todas las casillas marcadas y estado `implementada (T1-Tn completadas; aprobada por el propietario el <fecha>)`.
