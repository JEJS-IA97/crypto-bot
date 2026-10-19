# Hipótesis del cerebro

Ideas a probar en el torneo. Estado inicial: pendiente.

### Filtro de régimen para estrategias ORB
- Fecha: 2026-10-16 15:07 UTC · Estado: pendiente
- Por qué: Las estrategias de Opening Range Breakout (ORB) están siendo liquidadas por el ruido en regímenes de 'rango · vol alta'.
- Cómo probarla: Restringir las entradas de ORB NY solo cuando el ADX (14) en temporalidad de 15m sea superior a 25, indicando tendencia clara.

### Mitigación de 'Fee Drag' mediante Ratio R:B
- Fecha: 2026-10-16 15:07 UTC · Estado: pendiente
- Por qué: Con comisiones de 0.10% por lado, los scalps cortos son canibalizados por el costo transaccional.
- Cómo probarla: Añadir un filtro que descarte cualquier trade de 'Reversión al VWAP (5m)' si el objetivo de beneficio no es al menos 3 veces superior al costo de comisión esperado (0.20% del nocional).

### Priorización de temporalidades altas (H4) sobre intradía
- Fecha: 2026-10-16 15:07 UTC · Estado: pendiente
- Por qué: El backtest muestra que 'EMA 21/89 + RSI (4h)' tiene la esperanza matemática menos negativa (-0.008) comparada con el scalping.
- Cómo probarla: Ejecutar exclusivamente la estrategia de 4h durante los próximos 14 días y comparar la pendiente del equity curve contra las estrategias de 5m.

### Filtro de Umbral de Volatilidad ADX
- Fecha: 2026-10-17 02:28 UTC · Estado: pendiente
- Por qué: Las estrategias de ruptura fallan sistemáticamente en regímenes de 'rango · vol media' por falta de fuerza direccional.
- Cómo probarla: Añadir un filtro donde las estrategias de Ruptura de Bollinger solo operen si el ADX (14 periodos) es superior a 25 en temporalidad de 1h.

### Mitigación de Fricción por Timeframe
- Fecha: 2026-10-17 02:28 UTC · Estado: pendiente
- Por qué: Las estrategias de 5m generan una frecuencia de trades cuyo coste en comisiones supera el beneficio bruto esperado.
- Cómo probarla: Migrar la estrategia 'Reversión al VWAP' de 5m a 15m, manteniendo el riesgo por trade pero buscando un take profit mínimo de 3x el costo de la comisión.

### Optimización de Reversión en Rango
- Fecha: 2026-10-17 02:28 UTC · Estado: pendiente
- Por qué: En regímenes de rango, el RSI de 4h ha demostrado ser el filtro 'menos malo' en el backtest.
- Cómo probarla: Implementar una variante de la estrategia EMA 21/89 que solo ejecute entradas si el RSI (14) muestra divergencia confirmada en el gráfico de 1h.

### Filtro de inactividad por régimen en rango para estrategias intradía
- Fecha: 2026-10-17 10:03 UTC · Estado: pendiente
- Por qué: El backtest demuestra que 'rango · vol media' tiene expectativa negativa en todas las estrategias intradía; bloquear entradas en este entorno preservará capital.
- Cómo probarla: Implementar una regla cuantitativa en 'Reversión al VWAP (5m)' que inhabilite nuevas aperturas si el ADX(14) en 1h es inferior a 20 y el ATR(14) en 1h se sitúa en el tercil medio histórico.

### Ampliación de ratio riesgo-beneficio para absorber comisión del 0.20% round-trip
- Fecha: 2026-10-17 10:03 UTC · Estado: pendiente
- Por qué: Las estrategias de velas de 5 minutos sufren un 'drag' excesivo por comisiones fijas de 0.10 % por lado, reduciendo la expectativa por debajo de cero.
- Cómo probarla: Modificar 'ORB NY + filtro de tendencia' exigiendo un take profit mínimo fijo de 2.5R con stop loss a 1R, limitando la ejecución a setups donde el rango de ruptura sea al menos 3 veces el coste de comisión estimado.

### Migración a temporalidades superiores (Swing 4h) para reducir ratio comisiones/PnL
- Fecha: 2026-10-17 10:03 UTC · Estado: pendiente
- Por qué: 'EMA 21/89 + RSI (4h)' demostró la menor degradación en backtest (-3.63 % en 115 trades frente a >-60 % en intradía) debido al menor impacto relativo de comisiones por trade.
- Cómo probarla: Añadir al torneo una variante de 'EMA 21/89 + RSI' en gráfico de 4h que solo ejecute entradas a favor de la tendencia diaria (precio sobre SMA 200 en 1D) y evaluar tras 30 operaciones si el ratio fees/PnL bruto es inferior al 15 %.

### Implementación de filtro de régimen para 'rango · vol baja' con EMA 21/89 + RSI (4h)
- Fecha: 2026-10-17 15:25 UTC · Estado: pendiente
- Por qué: En el backtest a 365 días, EMA 21/89 + RSI (4h) fue la única configuración con esperanza positiva (+0.4258 USD/trade, n=37) en el régimen exacto en que se encuentran los cuatro activos.
- Cómo probarla: Añadir al torneo una variante de 'EMA 21/89 + RSI (4h)' restringida exclusivamente para abrir órdenes si el clasificador de mercado confirma régimen 'rango · vol baja', comparando su PnL neto tras 30 operaciones cerradas frente a las ejecuciones sin filtro.

### Inhibición de estrategias de ruptura (Bollinger y ORB) durante volatilidad baja
- Fecha: 2026-10-17 15:25 UTC · Estado: pendiente
- Por qué: Las estrategias 'Ruptura de Bollinger' y 'ORB' sufren constantes falsas rupturas en compresión de volatilidad, pagando comisiones de entrada y salida sin alcanzar recorridos de beneficio.
- Cómo probarla: Incorporar una regla de bloqueo que suspenda las entradas de 'Ruptura de Bollinger' y 'ORB NY' cuando el indicador ATR(14) en 1h se sitúe por debajo de su percentil 30 móvil de 20 períodos, midiendo la reducción del drawdown máximo y ahorro de fees frente a la versión base.

### Ampliación de objetivos en Reversión al VWAP (5m) para compensar el drag de comisiones
- Fecha: 2026-10-17 15:25 UTC · Estado: pendiente
- Por qué: Con comisiones del 0.10 % por lado (0.20 % round-trip), operar reversiones en 5m genera un profit factor inviable (0.09 en vivo, 0.57 en backtest) debido al reducido ratio beneficio/riesgo real tras costos.
- Cómo probarla: Testear una variante de 'Reversión al VWAP (5m)' que exija una desviación mínima de 2.5 desviaciones estándar de las bandas de VWAP y un ratio take-profit a stop-loss mínimo de 2:1 antes de disparar la orden, evaluando si el win rate ajustado supera el umbral de rentabilidad tras 50 trades.

### Filtro de volatilidad mínima (Umbral ATR)
- Fecha: 2026-10-17 19:25 UTC · Estado: pendiente
- Por qué: 
- Cómo probarla: Añadir un filtro que prohíba entradas si el ATR (14) en 1h es inferior al 0.5% del precio del activo.

### Migración a la ventaja estadística del backtest
- Fecha: 2026-10-17 19:25 UTC · Estado: pendiente
- Por qué: 
- Cómo probarla: Pausar sistemas de 5m y 15m y activar exclusivamente el setup de 4h en los 4 pares principales durante 10 operaciones.

### Optimización de Ratio Riesgo:Beneficio en Rango
- Fecha: 2026-10-17 19:25 UTC · Estado: pendiente
- Por qué: 
- Cómo probarla: Ajustar el Take Profit a un máximo de 1.5x el riesgo (R) y mover a Break Even tras alcanzar 1:1 de beneficio.

### Filtro de volatilidad mínima para reducción de ruido
- Fecha: 2026-10-17 23:25 UTC · Estado: pendiente
- Por qué: Las comisiones están neutralizando cualquier ganancia pequeña en regímenes de baja volatilidad.
- Cómo probarla: Añadir un filtro de ATR (14) en 5m; solo abrir operaciones si el ATR actual es superior al promedio de las últimas 100 velas.

### Migración a temporalidades mayores en regímenes de rango
- Fecha: 2026-10-17 23:25 UTC · Estado: pendiente
- Por qué: El backtest de 365d muestra que la EMA 21/89 + RSI en 4h es la única con esperanza positiva (0.42 USD/trade) en rangos.
- Cómo probarla: Desactivar Reversión al VWAP (5m) y activar EMA 21/89 + RSI (4h) en las cuentas de 100 USD para comparar recuperación.

### Optimización del Ratio Riesgo/Beneficio para compensar comisiones
- Fecha: 2026-10-17 23:25 UTC · Estado: pendiente
- Por qué: Con un Win Rate bajo en rupturas, el ratio R:R actual no compensa el 0.20% de comisión por trade completo.
- Cómo probarla: Ajustar el Take Profit a un mínimo de 3:1 R:R en la estrategia de Cruce EMA 9/21 y medir impacto en la curva de capital.

### Filtro de volatilidad mínima para rupturas
- Fecha: 2026-10-18 03:25 UTC · Estado: pendiente
- Por qué: 
- Cómo probarla: Añadir un filtro ADX (14 periodos) > 25 en temporalidad de 1h; solo permitir trades de ruptura si el ADX indica una tendencia naciente o fortalecida.

### Migración a marcos temporales altos (HTF) para mitigar fees
- Fecha: 2026-10-18 03:25 UTC · Estado: pendiente
- Por qué: 
- Cómo probarla: Sustituir las entradas de 5m por el setup EMA 21/89 en 4h, limitando la operativa a un máximo de 2 trades por par a la semana para reducir el impacto del churn de comisiones.

### Optimización del Ratio R:B en Reversión al VWAP
- Fecha: 2026-10-18 03:25 UTC · Estado: pendiente
- Por qué: 
- Cómo probarla: Modificar el take profit de la estrategia VWAP (5m) para que se ejecute estrictamente al alcanzar un R:B de 1:3, ignorando salidas prematuras excepto por stop loss.
