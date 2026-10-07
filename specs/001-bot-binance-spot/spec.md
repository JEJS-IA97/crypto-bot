# Spec 001 — Bot de trading Binance Spot con 20 USD (fase 1) — v3 (ORB)

> v2: incorpora las 4 decisiones del propietario y las correcciones de `clarificacion.md`.
>
> v3: la estrategia técnica pasa a **ORB** (rompimiento del rango de apertura
> 9:00–9:30 AM Nueva York sobre velas 5m) por decisión del propietario (D-11…D-14).
> Es la adaptación a Spot de una estrategia original de futuros MNQ (NASDAQ),
> que queda en reposo (constitución #1). EMA/RSI se conserva como candidata
> del backtest/grid-search (RF-15), sin emisión en el loop.

## Contexto y objetivo

El proyecto existe para que una persona con capital mínimo (20 USD) y poco conocimiento técnico
pueda operar cripto de forma disciplinada: el bot estudia el mercado, decide con reglas claras
(señales técnicas + señales externas/copy) y **nunca arriesga más de lo permitido**.

Fase 1 resuelve lo esencial y verificable: **un solo exchange (Binance Spot), 8 pares líquidos,
modo autónomo con panel web, riesgo acotado al detalle, y todo validado en simulación durante
1 mes antes de tocar dinero real**. El arbitraje multi-exchange, otras exchanges y las
transferencias entre cuentas quedan **en reposo congelado** (constitución #1-2 y RF-21).

Por qué así: con 20 USD el arbitraje entre exchanges no es viable (mínimos de orden + comisiones
de las dos piernas + coste de red se comen el margen), mientras que una estrategia direccional
acotada por stop sí es testeable y operable con ese capital.

## Decisiones del propietario (cerradas)
- D-1: Señales técnicas **+ copy** (señal externa manual/webhook) combinadas.
- D-2: Orden mínima de Binance + stop corto: inmoviliza ≈5 USDT, arriesga ≤1 USD.
- D-3: 8 pares líquidos: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, LINK.
- D-4: Señal externa pegada por el panel/webhook; el bot aplica sus reglas de riesgo.
- D-5: Paso a real: ≥1 mes simulado aprobado (RF-16) → testnet → real.
- D-6: Uso diario: autónomo + panel web con kill switch y métricas.
- D-7: Límite de capital = **sobre lo aportado** (las ganancias no bloquean).
- D-8: Pérdida diaria = 5% del valor de la cuenta al inicio del día UTC; al dispararse, **no se abren nuevas**, las abiertas conservan sus stops.
- D-9: Criterio de paso: PnL neto >0 tras comisiones, ≥15 operaciones, drawdown ≤10% y backtest positivo en validación y test.
- D-10: Multi-exchange/transferencias = **congelado** (intacto, tests en verde, sin tocar).
- D-11: **RR 1:1**: `TAKE_PROFIT_PCT = STOP_LOSS_PCT` (defecto 2.0% cada uno); el tamaño lo limitan RF-12/RF-13 (≤1 USD de riesgo por operación). Los "modos" tranquilo/agresivo de la estrategia original **no aplican** en Spot (sin contratos): un solo modo, acotado por la constitución.
- D-12: Pares ORB: **BTC, ETH, BNB, SOL**. XRP, DOGE, ADA y LINK siguen en la lista de 8 (D-3) pero **solo operan con señales externas** (copy, RF-8), sin señal técnica.
- D-13: En rompimiento **bajista** el bot no vende: Binance Spot sin cortos (constitución #1) → `HOLD`; solo se entra en rompimiento alcista (`BUY`).
- D-14: **Una sola señal ORB por par por día de Nueva York**, con ventana de entrada de 9:30 a 10:00 AM hora de Nueva York.

## Usuarios / actores
- **Propietario (tú):** necesita ver estado, métricas, parar el bot al instante y meter señales externas (copy) sin programar.
- **Bot:** evalúa mercado, decide, ejecuta, respeta límites y persiste toda decisión.
- **Binance (externo):** provee datos públicos (klines, exchangeInfo) y, en su fase, ejecuta órdenes.

## Historias de usuario
- H1: Como propietario quiero que el bot opere solo en simulación para validar la estrategia sin arriesgar dinero.
- H2: Como propietario quiero un botón que detenga el bot al instante para cortar pérdidas.
- H3: Como propietario quiero pegar una señal de un trader/grupo que sigo y que el bot la ejecute con mis reglas de riesgo para hacer copy trading sin estar pendiente.
- H4: Como propietario quiero ver métricas (rentabilidad, drawdown, operaciones) para decidir si paso a dinero real.
- H5: Como propietario quiero que ninguna pérdida diaria supere el 5% de mi cuenta para no quedarme sin fondos.

## Requisitos funcionales (criterios de aceptación en EARS)

### A. Modo de operación y seguridad del capital
- RF-1: MIENTRAS la variable `ALLOW_LIVE_TRADING` no valga `true`, EL SISTEMA opera únicamente en modo simulación (paper-trading) o testnet, y **no envía ninguna orden a producción**.
- RF-2: SI `ALLOW_LIVE_TRADING=true` pero el **aporte configurado** (`CONFIGURED_CAPITAL_USD`, inicio 20) excede lo autorizado o la fase activa no es `real` (RF-16), ENTONCES EL SISTEMA se niega a operar en real y expone el motivo en el panel. **El valor de la cuenta por ganancias nunca bloquea** (D-7); aportar más exige cambiar `CONFIGURED_CAPITAL_USD`.
- RF-3: EL SISTEMA ofrece un kill switch (endpoint + botón del panel) que detiene el loop de trading en caliente en ≤5 segundos sin reiniciar el proceso; MIENTRAS esté activado, EL SISTEMA no envía órdenes nuevas.
- RF-4: CUANDO la pérdida neta acumulada del día UTC alcance (≥) el 5% del valor de la cuenta a las 00:00 UTC, EL SISTEMA deja de **abrir posiciones nuevas** hasta las 00:00 UTC siguientes; las posiciones abiertas **conservan su stop-loss y take-profit**, y el estado se muestra como `bloqueado por pérdida diaria` en el panel. El contador se recalcula al arrancar el proceso con los datos persistidos (C6).
- RF-5: EL SISTEMA limita a **10 aperturas de posición por día UTC** y aplica cooldown de 300 s por par tras cada apertura; **stops y take-profits no cuentan como aperturas**; SI se supera, ENTONCES la apertura se rechaza y se registra el motivo.

### B. Datos de mercado y señales
- RF-6: CUANDO EL LOOP evalúa un ciclo, EL SISTEMA descarga las velas de **Binance `/api/v3/klines`** (temporalidad configurada, por defecto 15m, y cantidad de velas definida en `plan.md`) y `/api/v3/exchangeInfo` para los 8 pares (D-3), sin usar credenciales. **Adicionalmente**, MIENTRAS dure la ventana ORB (9:00–10:00 AM hora de Nueva York) EL SISTEMA descarga también velas de **5m** para los 4 pares ORB (D-12); cualquier fallo de esa descarga se trata igual que el resto: fail-closed por ciclo (RNF-6).
- RF-7 (v3 — estrategia ORB): EL SISTEMA genera la señal técnica con la estrategia de **rompimiento del rango de apertura (ORB)** sobre velas de 5m de BTC, ETH, BNB y SOL (D-12): el rango se forma con las **6 velas abiertas entre las 9:00 y las 9:30 AM de Nueva York** (`America/New_York`, horario de verano incluido) de cada día. CUANDO el reloj marca las **9:30 AM NY**, EL SISTEMA evalúa hasta las **10:00 AM NY**: SI el precio (cierre de la vela 5m en curso) supera el **máximo del rango**, ENTONCES emite `BUY` (motivo `orb_breakout_up`); SI queda por debajo del **mínimo del rango**, ENTONCES emite `HOLD` (motivo `breakdown_no_short`, D-13 — Binance Spot sin cortos); SI no hay rompimiento, falta alguna de las 6 velas del rango, aún no ha abierto la vela de las 9:30 o estamos fuera de la ventana, ENTONCES emite `HOLD` con su motivo (fail-closed). La señal es **determinista**: mismas velas + mismo instante + misma configuración → misma salida, verificable con test. La señal técnica **nunca emite `SELL`**: las posiciones se cierran por stop/take-profit (RF-13) o señal externa (RF-8). La estrategia EMA/RSI anterior queda **solo como candidata del backtest/grid-search** (RF-15), sin emisión en el loop.
- RF-8: EL SISTEMA acepta señales externas (copy) con formato `{symbol, side: "BUY"|"SELL", price_limit?, quantity?, quantity_quote?, source, ttl_seconds (defecto 300)}` por panel o webhook autenticado; SI `quantity`/`quantity_quote` no vienen, ENTONCES EL SISTEMA calcula el tamaño con RF-12; SI la señal está caducada (TTL) o `price_limit` se aleja del mercado más allá de `MAX_SIGNAL_PRICE_DISTANCE_PCT`, ENTONCES la rechaza; SI no pasa los mismos controles de riesgo que una señal técnica, ENTONCES la rechaza y responde con el motivo.
- RF-9: EL SISTEMA rechaza señales duplicadas (mismo `symbol`+`side` dentro del cooldown del par) y señales sobre pares fuera de la lista de 8.
- RF-10: CUANDO EL SISTEMA emite una decisión (técnica o externa) la persiste con timestamp, par, lado, origen (indicadores o fuente), **snapshot de mercado** (precio, velas/indicadores usados) y límites aplicados; CUANDO la posición se cierra, EL SISTEMA actualiza esa misma decisión con su resultado (PnL, comisiones, fills).
- RF-23: SI coexisten sobre el mismo par una decisión técnica y una externa en contrario, ENTONCES **prevalece la externa** (el propietario manda) y la técnica se persiste como `no ejecutada` con motivo `contradicha por señal externa`.
- RF-27: CUANDO ya existe una decisión técnica (origen `TECHNICAL`) para un par creada durante el **día de Nueva York en curso**, EL SISTEMA **no vuelve a evaluar ni emitir** otra señal técnica para ese par hasta el día NY siguiente (máximo 1 intento ORB por par por día, D-14); el primer intento —abierto, rechazado o contradicho— agota el día. Las posiciones abiertas siguen gestionándose con RF-13 y RF-8 con normalidad.

### C. Ejecución en Binance
- RF-11: CUANDO EL SISTEMA envía una orden, consulta `exchangeInfo` del par y respeta `LOT_SIZE`/`stepSize`, `PRICE_FILTER`/`tickSize` y el filtro de notional real (`MIN_NOTIONAL` o `NOTIONAL`); SI la orden no alcanza ese mínimo, ENTONCES no la envía y registra el motivo (sin valor fijo hardcodeado: A4).
- RF-12: EL SISTEMA calcula el tamaño de la orden como el **máximo entre el mínimo notional del par y el importe que respete el tope del 25% del aporte**, redondeado al `stepSize`; el **riesgo** no se controla con el tamaño sino con el stop (RF-13); máximo **3 posiciones abiertas simultáneas** (≤75% del aporte, duda abierta #3) y un solo activo por par (1 posición por `symbol`).
- RF-13: CUANDO una compra queda llena, EL SISTEMA coloca **inmediatamente** un stop-loss a la distancia configurada (`STOP_LOSS_PCT`) y un take-profit (`TAKE_PROFIT_PCT`) asociados (una sola posición por par, cancelando la orden contraria al llenarse la una u otra); SI con el tamaño de la orden la pérdida si salta el stop superara 1 USD, ENTONCES EL SISTEMA **reduce el tamaño o descarta la operación**; SI no consigue colocar el stop, ENTONCES considera la posición en `error`, lo alerta en el panel y no abre nuevas posiciones hasta resolverlo.
- RF-14: EL SISTEMA obtiene credenciales y `base_url` solo de variables de entorno; SI faltan credenciales en modo real, ENTONCES falla en modo seguro (sin órdenes) y lo indica en el panel.
- RF-24: EL SISTEMA aplica un **slippage máximo de 0.5%**: al confirmarse un fill, compara el precio ejecutado con el esperado; SI lo supera, ENTONCES registra el incidente y lo muestra en el panel (no aborta el cierre: el stop ya protege la posición).
- RF-25: EL SISTEMA verifica `clientOrderId` idempotente por decisión: SI un reintento reenvía la misma decisión, ENTONCES no genera una orden duplicada (RNF-5).

### D. Validación, métricas y fases
- RF-15: EL SISTEMA expone un backtest con split cronológico train/valid/test **sin look-ahead** que modela **comisión por lado del par (0.1%) y slippage configurable**, y reporta rentabilidad neta, drawdown máximo, número de operaciones y win rate; permite comparar configuraciones (grid search), incluida la candidata EMA/RSI. El backtest de la **estrategia activa (ORB)** entra en el rompimiento de las 9:30 AM NY y modela las salidas por take-profit/stop-loss de RF-13 (RR 1:1, D-11) dentro de la ventana del día.
- RF-16: EL SISTEMA registra la fase activa (`simulación` → `testnet` → `real`) en la base de datos, cambiable solo manualmente por el propietario; SI se solicita pasar de `simulación` a `testnet`, ENTONCES exige: **≥1 mes (30 días) de paper-trading con PnL neto >0 tras comisiones, ≥15 operaciones, drawdown ≤10% y backtest con signo positivo en validación Y test**; para pasar a `real` exige además testnet rentable; MIENTRAS no se cumplan, EL SISTEMA bloquea el cambio y muestra qué falta (D-9).
- RF-17: EL SISTEMA calcula y muestra en el panel con latencia ≤5 s tras la actualización: saldo, posiciones abiertas, PnL realizado/no realizado, drawdown actual, aperturas del día, pérdida del día y motivo de bloqueo si existe.
- RF-22: SI **5 ciclos consecutivos** fallan (excepción o datos caducados/invalidados), ENTONCES EL SISTEMA detiene el loop (circuit breaker), lo muestra en el panel y exige reinicio manual.
- RF-26: SI un take-profit o stop libera saldo, ENTONCES EL SISTEMA puede reabrir en el mismo par respetando cooldown, límite de aperturas del día y pérdida diaria (C7).

### E. Panel web (interfaz)
- RF-18: EL SISTEMA ofrece un panel que muestra: estado del bot (activo/detenido/bloqueado + fase), métricas (RF-17), historial de decisiones con su señal asociada y su resultado, y las señales rechazadas con su motivo. **"Notificar" = mostrar en el panel** (sin correo/Telegram en esta fase).
- RF-19: EL SISTEMA permite desde el panel: arrancar/detener el bot (kill switch) y enviar una señal externa (copy) validada, todo reflejado en la API REST.
- RF-20: EL SISTEMA protege con token (`API_TOKEN` en entorno) las rutas que **operan, reconfiguran, cambian de fase o resetean**; MIENTRAS la fase sea `real` o `testnet`, ENTONCES el token es obligatorio; en `simulación` es opcional (defecto: sin token). El token no se loguea ni se expone en respuestas (RNF-4).

### F. Fases en reposo (documentadas, no activas)
- RF-21: EL SISTEMA mantiene el área de arbitraje multi-exchange / transferencias **congelada**: el código existente y sus tests se dejan intactos y en verde, **sin refactorizar, ampliar ni mantenerlos** durante la fase 1; cualquier reactivación exige spec nueva aprobada (constitución #1-2, D-10).

## Requisitos no funcionales
- RNF-1: Todo importe, cantidad y precio se manipula en `Decimal`; prohibido `float` para valores monetarios.
- RNF-2: La suite de tests corre **sin red y sin credenciales** (httpx y clientes mockeados); cualquier test que necesite Binance real se marca y no forma parte de la suite diaria.
- RNF-3: El loop de trading no bloquea la API REST (la API responde mientras el bot evalúa).
- RNF-4: Secretos únicamente en `.env` (fuera de git); nunca se loguean claves ni firmas.
- RNF-5: Toda orden es idempotente: un reintento nunca genera una orden duplicada (`clientOrderId` único por decisión).
- RNF-6: Disponibilidad degrada con seguridad: SI Binance no responde o los datos están caducados, ENTONCES el bot no opera en ese ciclo (fail-closed) y lo registra; cinco fallos seguidos → RF-22.
- RNF-7: Código e identificadores en inglés; documentación, mensajes de UI y esta spec en español.

## Casos límite
- **ORB — horario de verano**: la ventana usa `America/New_York`; en invierno (EST, UTC-5) el rango empieza a las 14:00 UTC y en verano (EDT, UTC-4) a las 13:00 UTC. Una sola implementación de zona horaria, comprobada por test en ambas estaciones.
- **ORB — reinicio/caída del bot**: si al volver el proceso ya pasaron las 10:00 AM NY, no hay señal ese día (`breakout_window_closed`); nunca se entra fuera de la ventana.
- **ORB — vela del rango ausente**: si falta alguna de las 6 velas de 9:00–9:30 (reinicio en mitad de la ventana, datos caducados), el día queda sin señal (`range_incomplete`, fail-closed).
- **ORB — segundo intento el mismo día**: deduplicado por RF-27, sin crear filas nuevas en la BD.
- **ORB — rompimiento bajista**: `HOLD` (`breakdown_no_short`), nunca `SELL` (D-13, Spot sin cortos).
- **ORB — pares no ORB** (XRP, DOGE, ADA, LINK): sin señal técnica; solo señales externas (D-12).
- Binance caído o con rate limit durante el loop → fail-closed por ciclo (RNF-6) y circuit breaker a los 5 fallos (RF-22).
- Precio del par con congelación/suspensión (`status ≠ TRADING`) → se excluye y se registra.
- Saldo insuficiente o por debajo del mínimo notional → rechazo con motivo, sin reintentos ciegos.
- Señal duplicada o del mismo lado dentro del cooldown → rechazada (RF-9); señales **opuestas** → prevalece la externa (RF-23).
- Señal externa caducada o con precio lejano → rechazada con motivo (RF-8).
- Corte de proceso en mitad de una orden → al arrancar, se reconcilian órdenes **y posiciones** con el exchange y se restaura el contador de pérdida diaria desde la BD antes de operar.
- Kill switch pulsado mientras hay una orden en vuelo → se detienen órdenes nuevas; las existentes se monitorizan y se reportan.
- Pérdida diaria alcanzada en la operación N → se registra el bloqueo, no se abren nuevas, los stops vigentes siguen activos hasta mañana (UTC).
- Fill con slippage >0.5% → incidente registrado y visible (RF-24).
- Comisiones: simulación y backtest descuentan 0.1% por lado; sin esto las métricas no sirven (RF-15).
- Precios escritos a mano del panel actual → **eliminado**; el panel usa precios reales (RF-17).

## Fuera de alcance (fases en reposo, ver RF-21)
- Otras exchanges (OKX, Bybit, Kraken, Coinbase) y arbitraje entre ellas — **en reposo congelado**.
- Transferencias/retiros entre exchanges o entre billeteras — **en reposo congelado** (al reactivarse exige spec nueva: constitución #1).
- Futuros, margen, apalancamiento, short — descartado por la constitución #1.
- Estrategia original sobre **futuros MNQ/NQ (NASDAQ)** — en reposo: su adaptación a Spot es la estrategia ORB de RF-7; operar derivados exige spec nueva (constitución #1-2).
- Modelos de ML predictivos sin métrica demostrada — la fase 1 usa reglas + backtest/grid-search (constitución #9); un modelo ML entra con spec propia cuando haya datos suficientes.
- Copy trading automático vía API de Binance (no existe para quien copia) — resuelto con señal externa manual/webhook (RF-8).
- Notificaciones fuera del panel (correo/Telegram/push) — RF-18.
- Múltiples cuentas de usuario, registro/login masivo, app móvil.

## Criterios de finalización
- [x] Todos los RF tienen al menos un test que los cubre. (T24: mapeo RF→test verificado, 27/27)
- [x] Todos los RNF verificables están medidos. (suite sin red/credenciales, Decimal, compileall)
- [x] Los casos límite están cubiertos. (ORB DST/caídas/rango ausente, fail-closed, circuit breaker…)
- [x] La suite de tests pasa en verde. (T24: 252 tests OK + ruff)
- [x] No hay código sin RF que lo justifique. (T24: módulos M1-M14, zona congelada RF-21 y specs 002/003/004)
- [ ] Paper-trading ≥30 días con PnL >0, ≥15 operaciones, drawdown ≤10% y backtest aprobado antes de fase `testnet` (RF-16).

## Dudas abiertas
- [NECESITA ACLARACIÓN] ¿Parámetros finales de ORB (ventana, `STOP_LOSS_PCT`/`TAKE_PROFIT_PCT`, pares) y de la candidata EMA/RSI? Se deciden en `plan.md` a partir del backtest sobre datos reales (RF-15), no a ojo.
- [NECESITA ACLARACIÓN] ¿Fuente concreta de las señales externas (grupo/trader/TradingView) y su formato exacto? RF-8 define el contrato mínimo que debe cumplir.
- [NECESITA ACLARACIÓN] ¿Máximo de 3 posiciones abiertas (75% del aporte) o 2 (50%) dejando más colchón? (RF-12 usa 3 por ahora.)
