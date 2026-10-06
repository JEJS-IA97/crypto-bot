# Clarificación QA — Spec 001 (Fase 3)

Revisión profesional de `spec.md`. **Solo detecta, no resuelve.** Cada hallazgo se marca con severidad:
- **[BLOQUEANTE]** impide implementar sin una decisión humana.
- **[ALTA]** ambigüedad que produciría código dudoso o no testeable.
- **[MEDIA]** incompleto pero implementable con criterio.

## A. Contradicciones

- **A1 [BLOQUEANTE] — RF-2 vs RF-16 y objetivo del proyecto.** RF-2 prohíbe operar en real si "el capital configurado excede 20 USD", pero el objetivo declarado es *crecer el capital*. Si el bot gana y la cuenta pasa a 22 USD, RF-2 la bloquearía. Falta definir: ¿el límite es sobre lo aportado (20 USD) o sobre el valor de la cuenta? Tampoco está definido si una nueva aportación manual cambia ese límite.
- **A2 [ALTA] — RF-12 mezcla dos conceptos.** "Tamaño = `max(mínimo notional, riesgo permitido)`" combina un notional (5 USDT) con un riesgo (pérdida ≤1 USD): son unidades distintas y, en la práctica, `max()` siempre devuelve el mínimo notional → la fórmula no decide nada.
- **A3 [ALTA] — RF-5 vs RF-16: ¿qué es "una operación"?** RF-5 limita a "10 operaciones/día" pero no dice si cuenta órdenes (compra, venta, stop, take-profit) o ciclos compra→venta. Con stops y takes, el límite se agotaría en pocas horas si son órdenes.
- **A4 [MEDIA] — RF-11 "≈5 USDT".** El mínimo real es `MIN_NOTIONAL`/`NOTIONAL` de `exchangeInfo` y varía por par (y puede cambiar). Especificar un aproximado fijo contradice RF-11 misma (que manda leer `exchangeInfo`).

## B. Ambigüedades (no verificables tal cual)

- **B1 [BLOQUEANTE] — RF-4 pérdida diaria sin base de cálculo.** No dice: ¿5% sobre el capital inicial (1 USD) o sobre el valor actual de la cuenta?; ¿se mide el PnL neto del día o el máximo desde el pico intradía?; ¿≥ o >?; ¿y si a las 00:00 UTC quedan posiciones abiertas: se cierran, se dejan con su stop, o el bot solo deja de abrir nuevas? Sin esto, RF-4 no tiene test posible.
- **B2 [ALTA] — RF-13 sin criterio de cálculo del stop/tp.** "Según la configuración activa" no define cómo se coloca el stop (distancia fija %, ATR, precio de entrada − X). Tampoco: ¿qué pasa si se llena el take-profit y el stop sigue vivo (¿se cancela?); ¿órdenes parciales permitidas?; ¿un solo stop/tp por posición?
- **B3 [ALTA] — RF-6/RF-7 sin fuente ni temporalidad.** No se especifica endpoint de OHLCV (`/api/v3/klines` u otro) ni timeframe de velas (1m/5m/15m/1h) ni cuántas velas se usan. Afecta a la determinismo de RF-7: sin timeframe no hay "mismos datos → misma señal" definible.
- **B4 [ALTA] — RF-8 señales externas incompletas.** No define: enum de `lado` (¿BUY/SELL o compra/venta?), TTL de la señal (¿una señal de hace 3 h sigue siendo válida?), quién calcula la cantidad si no viene en el payload, y si un precio límite muy alejado del mercado se acepta o se rechaza.
- **B5 [BLOQUEANTE] — RF-16 criterio de "aprobado" vago.** "Rentable" no está definido (¿PnL > 0? ¿> 1%? ¿tras comisiones?), no hay mínimo de operaciones para que el mes tenga valor estadístico (¿y si en 1 mes solo hay 3 operaciones?), ni criterio de "backtest aprobado" (¿que validación y test den signo positivo? ¿máxima divergencia entre ellas?).
- **B6 [MEDIA] — RF-10 mezcla dos momentos.** Pide persistir "resultado" junto a la decisión, pero el resultado no existe al decidir. Debería separarse: persistir la decisión al emitirla y actualizar su resultado al cerrarse. Tampoco define qué contiene "el snapshot de precio" (solo precio, ¿o también indicadores y velas?).
- **B7 [MEDIA] — RF-20 autenticación a medias.** No dice si **testnet** exige token, quién define/guarda el token, ni lista las rutas protegidas ("las que operan o reconfiguran" es impreciso).
- **B8 [MEDIA] — RF-4/RF-18 "notifica".** Ambiguo: ¿solo en el panel? ¿correo/Telegram/push? Si no está en el alcance, debe decir "muestra en panel".
- **B9 [MEDIA] — RF-17 "tiempo casi real".** No medible → no testeable. Definir latencia máxima (p.ej. ≤5 s tras un refresh).
- **B10 [ALTA] — RF-21 alcance incierto.** "Simulable en paper-trading y con sus tests": ¿significa mantener el simulador multi-exchange **funcionando y en verde** durante toda la fase 1 (coste de mantenimiento), o **congelado** (tests existentes, sin tocarlo)? Define si hay que refactorizar el código actual de arbitraje o solo dejarlo intacto.

## C. Casos límite ausentes

- **C1 [ALTA]** — Señales **opuestas** simultáneas sobre el mismo par (técnica BUY vs externa SELL): RF-9 solo trata duplicados del mismo lado. Falta regla de prioridad.
- **C2 [ALTA]** — **Slippage máximo en ejecución**: los stops son órdenes a mercado y el precio de relleno real es desconocido; no existe RF de slippage permitido (el código actual tenía 0.2% pero la spec no lo recoge).
- **C3 [ALTA]** — **Fallos repetidos del loop**: si Binance falla 5 ciclos seguidos no hay circuit breaker; solo hay fail-closed por ciclo (RNF-6).
- **C4 [ALTA]** — **Comisiones**: no se dice si la simulación/backtest modela comisión por lado (0.1%) ni cómo se pagan (¿en BNB con descuento?). Sin esto, toda métrica es irrelevante.
- **C5 [MEDIA]** — **Persistencia de la fase activa**: RF-16 habla de fases pero no dice dónde se guarda (`env`/BD) ni quién puede cambiarla (¿solo manualmente y con las evidencias?).
- **C6 [MEDIA]** — **Reinicio con posiciones abiertas**: RF y casos límite cubren reconciliar *órdenes* tras un corte, pero no *posiciones*, ni **restaurar el contador de pérdida diaria** (¿o el límite se reinicia con el proceso y se evita?).
- **C7 [MEDIA]** — **Reinversión**: cuando un stop/tp libera USDT, ¿puede el bot reabrir en el mismo par el mismo día? (RF-5 cooldown lo sugiere, pero no está explícito para ventas.)

## D. Conflictos con la constitución

- **D1 [BLOQUEANTE]** — RF-2/constitución #3 ("máximo 20 USD reales en total") bloquean cualquier crecimiento por encima de 20 USD, contradiciendo el objetivo explícito del usuario de *seguir aportando y crecer*. Requiere decisión humana: o se reformula la constitución #3, o se interpreta el límite como aporte inicial.
- Sin más conflictos detectados: kill switch (const. #5 ↔ RF-3), auditoría (const. #10 ↔ RF-10), fase real doble-check (const. #5 ↔ RF-1/RF-2), tests/spec (const. #7-8) y Decimal (const. #11 ↔ RNF-1) quedan cubiertos.

## Resumen
- Bloqueantes: **A1, B1, B5, D1** (4) — necesitan decisión del propietario.
- Altas: **A2, A3, B2, B3, B4, B10, C1, C2, C3, C4** (10)
- Medias: **A4, B6, B7, B8, B9, C5, C6, C7** (8)

## Estado de resolución (post-entrevista, spec v2)

| Hallazgo | Estado | Cómo quedó en `spec.md` |
|---|---|---|
| A1 / D1 (límite 20 USD vs crecer) | **Resuelto — decisión D-7** | RF-2: límite sobre el aporte configurado; las ganancias no bloquean. Constitución #3 reformulada. |
| B1 (pérdida diaria) | **Resuelto — decisión D-8** | RF-4: 5% del valor a las 00:00 UTC, ≥; deja abrir nuevas, conserva stops; contador restaurado al arrancar. |
| B5 (criterio de paso) | **Resuelto — decisión D-9** | RF-16: ≥30 días, PnL>0 tras comisiones, ≥15 ops, drawdown ≤10%, backtest + en valid y test. |
| B10 (alcance reposo) | **Resuelto — decisión D-10** | RF-21: congelado, intacto, tests en verde, sin tocar. |
| A2 (fórmula tamaño/riesgo) | Corregido | RF-12: tamaño = máx(mínimo notional, 25% del aporte) redondeado al step; riesgo lo controla el stop (RF-13). |
| A3 (qué es "operación") | Corregido | RF-5: cuenta aperturas de posición; stops/tp no cuentan. |
| A4 (≈5 USDT hardcodeado) | Corregido | RF-11: filtro `MIN_NOTIONAL`/`NOTIONAL` leído de `exchangeInfo`, sin valor fijo. |
| B2 (stop/tp sin criterio) | Corregido | RF-13: distancias en % por configuración, una posición por par, cancelación cruzada, tope de 1 USD, estado `error` si falla el stop. |
| B3 (sin fuente/temporalidad) | Corregido | RF-6: `/api/v3/klines` + `exchangeInfo`, temporalidad por defecto 15m (cantidad de velas en plan). |
| B4 (señal externa incompleta) | Corregido | RF-8: enum `side`, TTL 300 s, cálculo de cantidad si falta, rechazo por precio lejano. |
| B6 (decisión vs resultado) | Corregido | RF-10: persiste al emitir, actualiza resultado al cerrar; snapshot = precio + velas/indicadores. |
| B7 (auth a medias) | Corregido | RF-20: token en fases `testnet`/`real` para rutas de operación/reconfiguración/fase/reset; opcional en simulación. |
| B8 ("notifica") | Corregido | RF-18: notificar = mostrar en panel; correo/Telegram fuera de alcance. |
| B9 ("casi real") | Corregido | RF-17: latencia ≤5 s tras actualización. |
| C1 (señales opuestas) | Corregido | RF-23: prevalece la externa; la técnica queda `no ejecutada` con motivo. |
| C2 (slippage) | Corregido | RF-24: máximo 0.5%, incidente registrado y visible. |
| C3 (fallos seguidos) | Corregido | RF-22: circuit breaker a los 5 fallos consecutivos, reinicio manual. |
| C4 (comisiones) | Corregido | RF-15: backtest y simulación modelan 0.1% por lado + slippage configurable. |
| C5 (dónde vive la fase) | Corregido | RF-16: fase en BD, cambio solo manual. |
| C6 (reinicio con posiciones) | Corregido | RF-4 + casos límite: reconciliar posiciones y restaurar contador diario. |
| C7 (reinversión tras tp/stop) | Corregido | RF-26: permitida respetando cooldown, aperturas/día y pérdida diaria. |

