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

### Inmunidad a comisiones en marcos diarios
- Fecha: 2026-10-20 20:36 UTC · Estado: pendiente
- Por qué: Las estrategias en 1d realizan pocos giros y promedian ganancias sustancialmente mayores al costo de 0,20 % round-trip.
- Cómo probarla: Evaluar tendencia en 1d con cruces lentos y stops amplios contra backtest de 365 días.

### Momentum de medio plazo en activos directores
- Fecha: 2026-10-20 20:36 UTC · Estado: pendiente
- Por qué: Pares como BNB y DOGE muestran tendencia activa; un filtro de momentum porcentual en 1d captura tramos limpios.
- Cómo probarla: Monitorear tasa de acierto y factor de beneficio de momentum lookback 20 en 1d en régimen de tendencia.

### Transición a 4h en seguimiento de tendencia para estabilizar Monte Carlo
- Fecha: 2026-10-21 10:55 UTC · Estado: pendiente
- Por qué: Las medias móviles en 1d tienen un Sharpe aparente alto pero muy pocos trades, haciendo que el remuestreo de Monte Carlo falle; bajar a 4h multiplica las observaciones preservando capturas de tendencia superiores al 3 %.
- Cómo probarla: Evaluar tendencia 4h con medias intermedias (34 y 144) sobre activos actualmente tendenciales como BNB y LTC.

### Ruptura de canal Donchian multidiario (4h) con R:R asimétrico
- Fecha: 2026-10-21 10:55 UTC · Estado: pendiente
- Por qué: Un canal de 48 períodos en 4h equivale a los máximos de 8 días; con stop de 2,0 ATR y target de 5,0 ATR se protege contra falsas salidas y se cubre holgadamente la comisión spot.
- Cómo probarla: Backtest de donchian 4h n=48 filtrando salidas prematuras con ATR amplio.

### Reversión extrema a la media en 1h adaptada al régimen de rango
- Fecha: 2026-10-21 10:55 UTC · Estado: pendiente
- Por qué: Los activos principales están en rango; entradas únicamente en sobreventa extrema (RSI < 25) evitan trampas bajistas y permiten rebotar hacia el centro de la distribución.
- Cómo probarla: Testear reversion 1h con rsi_low en 22 y ratio TP/SL mayor a 1.5 en pares en rango.

### Cluster tendencial robusto en marco diario
- Fecha: 2026-10-21 14:55 UTC · Estado: pendiente
- Por qué: Las combinaciones de medias móviles rápidas (59-88) y lentas (124-184) en 1d han mostrado los únicos PF > 30 y retornos positivos consistentes, amortiguando completamente el arrastre de comisiones.
- Cómo probarla: Ejecutar backtest y prueba Monte Carlo con parámetros centrados en fast=72 y slow=150 en 1d evitando la zona rechazada 65/160.

### Momentum de mediano plazo en 4h para balancear frecuencia y fricción
- Fecha: 2026-10-21 14:55 UTC · Estado: pendiente
- Por qué: Momentum en 1d generó rechazo por MC p95 del 100% debido a escasez de muestras; una ventana intermedia de 4h con umbral moderado de retorno puede capturar swings sin sobreoperar.
- Cómo probarla: Testear momentum en 4h con lookback=36 y min_ret=0.04 sobre activos en régimen de tendencia como BTC y BNB.

### Eficiencia del seguimiento de tendencia en 1d con ventana media-larga
- Fecha: 2026-10-22 12:28 UTC · Estado: pendiente
- Por qué: Las mutaciones exitosas (59/139, 77/124, 90/163) demuestran que una rápida >= 60 y lenta entre 125-170 neutralizan el ruido de mercado y reducen los costes de transacción a mínimos viables.
- Cómo probarla: Validar combinaciones en 1d cercanas a los núcleos ganadores de mutación, evaluando rigurosamente el drawdown p95 en Monte Carlo para evitar caídas catastróficas.

### Momentum de mediano plazo en 1d para filtrar consolidaciones
- Fecha: 2026-10-22 12:28 UTC · Estado: pendiente
- Por qué: El momentum de lookback corto (21d) generó drawdowns inaceptables, pero un lookback más extenso (>= 40d) junto con un umbral de retorno moderado puede capturar fases macro alcistas sin sobreoperar.
- Cómo probarla: Evaluar momentum en 1d con lookback de 42 días y retorno mínimo de 5 %, comprobando que supere el umbral de transacciones y rentabilidad positiva en entrenamiento.

### Resonancia en EMA RSI sobre 4h inspirada en la estrategia líder
- Fecha: 2026-10-25 11:56 UTC · Estado: pendiente
- Por qué: La configuración 21/89 en 4h ha demostrado ser la única rentable en tiempo real en entornos de baja volatilidad.
- Cómo probarla: Evaluar una parametrización cercana en ema_rsi con ratios asimétricos de TP/SL para capturar expansiones respetando el rango.

### Persistencia del momentum diario en activos seleccionados
- Fecha: 2026-10-25 11:56 UTC · Estado: pendiente
- Por qué: Momentum 1d con lookback intermedio y umbral positivo fue previamente validado en BNB con PF de 2.72.
- Cómo probarla: Testear un lookback de 35 días con un umbral de retorno de 5% en 1d para filtrar ruido intradiario.

### Zona óptima de cruce diario lento para mitigar drawdown Monte Carlo
- Fecha: 2026-10-25 11:56 UTC · Estado: pendiente
- Por qué: Los modelos de tendencia 1d con medias lentas entre 160 y 180 y rápidas sobre 70 han logrado superar el examen sin sobreajuste.
- Cómo probarla: Simular un cruce 70/175 en 1d para mantener baja rotación y amortiguar los costes por comisión.

### Pullbacks con confirmación RSI en 4h filtran falsos quiebres en rangos
- Fecha: 2026-10-27 22:00 UTC · Estado: pendiente
- Por qué: La configuración EMA 21/89 con RSI en 4h sobrevive al entorno lateral porque exige retroceso y sobreventa relativa antes de comprar, a diferencia del Donchian que compra techos.
- Cómo probarla: Backtest en 365d de EMA RSI en 4h acotando stop_atr a 2.0 y testeando ratios riesgo/beneficio mayores a 2.0.

### Momentum diario con filtro de retorno mínimo aísla activos con flujo real
- Fecha: 2026-10-27 22:00 UTC · Estado: pendiente
- Por qué: Con la mayoría de pares en rango, solo aquellos con retornos acumulados superiores al 7-10 % en 30-50 días poseen suficiente inercia para compensar las comisiones spot.
- Cómo probarla: Evaluar momentum en 1d con lookback entre 30 y 50 y min_ret >= 0.08 sobre ETH, XRP y BNB.

### Momentum de ciclo intermedio en TF diario filtra el ruido lateral
- Fecha: 2026-10-28 02:00 UTC · Estado: pendiente
- Por qué: Un lookback cercano a 30 días en gráfico diario logra capturar tendencias reales como las de XRP/LINK evitando la volatilidad intradía de los rangos.
- Cómo probarla: Evaluar momentum en 1d con lookback=30 y umbral mínimo de retorno de 0.05 sobre el universo spot.

### Donchian de período largo en 4h reduce falsas entradas en consolidación
- Fecha: 2026-10-28 02:00 UTC · Estado: pendiente
- Por qué: Ampliar la ventana de Donchian a 90 períodos exige rupturas más consolidadas, reduciendo trades perdedores en rangos.
- Cómo probarla: Simular Donchian breakout en 4h con n=90 y un stop ATR holgado de 2.5.

### Reversión a la media en 15m para corregir sub-muestreo
- Fecha: 2026-10-28 06:00 UTC · Estado: pendiente
- Por qué: La configuración previa en 1h generó apenas 7 trades; reducir a 15m capturará oscilaciones intradía típicas del régimen de rango sin penalizar en exceso comisiones.
- Cómo probarla: Backtest de 365 días en Binance spot con rsi_low=28, stop_atr=1.5 y tp_atr=2.2 evaluando un mínimo de 50 operaciones y PF > 1.3.

### EMA + RSI en 1h alineado a la duración mediana de traders líderes (19h)
- Fecha: 2026-10-28 06:00 UTC · Estado: pendiente
- Por qué: Los traders más consistentes cierran trades en torno a 19-26h; un filtro EMA/RSI en 1h captura este horizonte temporal mejorando la agilidad frente al 4h.
- Cómo probarla: Evaluar fast=14, slow=70 en tf 1h contrastando métricas de expectancy y drawdown respecto al modelo de 4h.

### Momentum relativo en 4h sobre activos seleccionados
- Fecha: 2026-10-28 06:00 UTC · Estado: pendiente
- Por qué: DOGE, LINK y AVAX mantienen regímenes tendenciales a pesar del letargo de BTC/ETH, haciendo propicio el momentum en 4h con umbral moderado.
- Cómo probarla: Ejecutar momentum lookback=30 y min_ret=0.06 en 4h filtrando por pares con régimen de tendencia.

### Sistemas EMA+RSI en 4h aprovechan mejor las tendencias con baja volatilidad
- Fecha: 2026-10-28 10:00 UTC · Estado: pendiente
- Por qué: El único modelo con retorno positivo constante en el ranking vivo es EMA 21/89 + RSI en 4h, filtrando entradas falsas.
- Cómo probarla: Evaluar la combinación de cruces de medias móviles rápidas/lentas con filtro RSI en timeframes de 4h con parámetros de TP moderados.

### Filtros Donchian en 1h con TP ajustado capturan micro-tendencias sin sobreexposición
- Fecha: 2026-10-28 10:00 UTC · Estado: pendiente
- Por qué: Reducir la ventana N a 40 períodos en 1h permite entrar antes que en 4h evitando fallas por bajo volumen.
- Cómo probarla: Correr backtest de Donchian 1h con N=40 y ratio R:R de 1:2.

### Reversión a la media con RSI extremo en 15m
- Fecha: 2026-10-28 14:00 UTC · Estado: pendiente
- Por qué: Dado el régimen de rango predominante, capturar agotamientos en niveles extremos de RSI (<=20) con stops ceñidos puede capturar rebotes sin quedar atrapado en tendencias falsas.
- Cómo probarla: Validar backtest en 15m exigiendo rsi_low=20 y ratio beneficio/riesgo prudente (1.2 stop / 2.0 tp).

### Canales Donchian más estrechos con R/R moderado
- Fecha: 2026-10-28 14:00 UTC · Estado: pendiente
- Por qué: Los canales largos (90 periodos) fallaron por tardíos. Un canal de 30 periodos en 4h puede capturar pequeños micro-impulsos dentro del rango.
- Cómo probarla: Evaluar Donchian n=30 en 4h comprobando si reduce el impacto de las tarifas y mejora el PF.

### Filtro de momentum con umbral elevado en 4h
- Fecha: 2026-10-28 18:00 UTC · Estado: pendiente
- Por qué: Los mercados en rango penalizan las rupturas débiles; exigir mayor aceleración reduce operaciones falsas.
- Cómo probarla: Implementar familia momentum en tf 4h con min_ret superior a 0.08 y lookback medio.

### Optimización de medias móviles rápidas con control ATR
- Fecha: 2026-10-28 18:00 UTC · Estado: pendiente
- Por qué: La combinación de cruces con stop loss dinámico basado en volatilidad protege el capital en rangos estrechos.
- Cómo probarla: Probar la familia ema_rsi en tf 4h ajustando fast/slow hacia la zona validada por el éxito previo.

### Filtro RSI en TF de 4h reduce falsas rupturas en mercados laterales
- Fecha: 2026-10-28 22:00 UTC · Estado: pendiente
- Por qué: La estrategia líder en vivo (EMA 21/89 + RSI 4h) demuestra que exigiéndole confirmación de impulso al RSI se evitan entradas durante rangos estrechos.
- Cómo probarla: Evaluar una variante de ema_rsi con TF 4h, parámetros intermedios y una relación riesgo-beneficio de al menos 1:2.

### Momentum diario con lookback amplio aísla activos con tendencia real
- Fecha: 2026-10-28 22:00 UTC · Estado: pendiente
- Por qué: El momentum en 4h falla constantemente por el ruido intradía, pero una ventana más amplia en 1d captura movimientos sostenidos como el de LTC.
- Cómo probarla: Probar momentum en 1d con lookback de 40 días y filtro de retorno mínimo del 8%.

### Filtro RSI en TF medio atenúa falsas entradas en rango
- Fecha: 2026-10-29 02:00 UTC · Estado: pendiente
- Por qué: Las medias móviles por sí solas compran techos localmente en mercados en rango. Exigir RSI en zona óptima reduce operaciones perdedoras.
- Cómo probarla: Evaluar la familia ema_rsi en TF 4h ajustando parámetros de medias moderadas (15/75).

### Migración de Reversión a 1h para reducir impacto de comisiones
- Fecha: 2026-10-29 02:00 UTC · Estado: pendiente
- Por qué: En 15m el ruido genera demasiadas señales falsas y pocos trades limpios tras fees. En 1h la relación riesgo/beneficio es más estable.
- Cómo probarla: Probar reversión con rsi_low en 25 en timeframe 1h con Take Profit holgado.

### Momentum diario calibrado a menor umbral supera el umbral de rentabilidad
- Fecha: 2026-10-29 10:56 UTC · Estado: pendiente
- Por qué: El momentum 1d previo (lookback 40, min_ret 0.08) obtuvo PF 0.97. Reducir ligeramente el filtro de retorno exigido a 0.04 y acortar el lookback a 30 días permitirá capturar giros con menor retraso evitando los falsos quiebres intradía.
- Cómo probarla: Entrenar momentum en 1d con lookback 30 y min_ret 0.04 evaluando si el PF supera 1.20 con al menos 15 trades históricos.

### Filtro RSI en 1h con stop amplio sobrevive al régimen de rango y volatilidad
- Fecha: 2026-10-29 10:56 UTC · Estado: pendiente
- Por qué: Dado el éxito vivo del modelo EMA/RSI en 4h, trasladar la lógica a 1h con stop_atr de 2.5 y tp_atr de 5.0 generará mayor frecuencia estadística sin quedar atrapado en el ruido de 15m.
- Cómo probarla: Comparar métricas en entrenamiento de ema_rsi 1h (13/65) contra el benchmark de 4h exigiendo factor de beneficio > 1.3.

### Filtro oscilatorio RSI previene trampas de mercado lateral en cruces EMA
- Fecha: 2026-10-29 14:56 UTC · Estado: pendiente
- Por qué: La estrategia EMA 21/89 + RSI en 4h es la única con retorno positivo constante en el torneo en vivo mientras las demás fallan.
- Cómo probarla: Validar variantes de cruces EMA en temporalidad 4h combinados con exigencias de RSI en sobreventa/impulso y objetivos de ganancia holgados en ATR.

### Reversión extrema en 15m supera el problema de baja frecuencia de trades
- Fecha: 2026-10-29 14:56 UTC · Estado: pendiente
- Por qué: La idea previa de reversión en 1h fue rechazada por realizar solo 7 operaciones; reducir el timeframe a 15m debería aumentar la muestra manteniendo la ventaja en rangos.
- Cómo probarla: Evaluar una estrategia de reversión en 15m con RSI muy bajo (< 20) sobre pares en rango de alta volatilidad como BNB, LINK o LTC.

### Filtrado por RSI previene entradas en techos durante rangos volátiles
- Fecha: 2026-10-29 18:56 UTC · Estado: pendiente
- Por qué: La combinación de medias móviles de medio/largo plazo junto con filtro RSI en TF de 4h evita comprar cuando el precio ya está agotado al borde del rango superior.
- Cómo probarla: Probar un experimento con ema_rsi en 4h utilizando EMA rápida de 21 y lenta de 89 con un TP/SL ajustado a volatilidad por ATR.

### Reversión en 1h con RSI menos restrictivo aumenta frecuencia sin perder precisión
- Fecha: 2026-10-29 18:56 UTC · Estado: pendiente
- Por qué: Un umbral rsi_low de 25 o inferior generaba muy pocos trades (rechazado en memoria); elevarlo a 30 en 1h captura mejores rebotes impulsivos en volatilidad alta.
- Cómo probarla: Evaluar la familia reversion en TF 1h fijando rsi_low en 30 y un TP ATR de 3.0 para superar el impacto del 0.10% de comisión por lado.

### Filtro RSI en swing 4h neutraliza el ruido del rango volátil
- Fecha: 2026-10-30 01:27 UTC · Estado: pendiente
- Por qué: En marcos de 4h, combinar el cruce EMA con RSI evita comprar sobreextensiones dentro del rango y captura impulsos con mayor recorrido que el stop ATR.
- Cómo probarla: Validar en backtest con comisiones 0.10 %/lado comparando un cruce EMA puro frente a EMA + RSI con TP >= 2x SL.

### Transición de tendencia de 1d a 4h reduce el drawdown por retardo
- Fecha: 2026-10-30 01:27 UTC · Estado: pendiente
- Por qué: Las medias en 1d tardan demasiado en girar y sufren whipsaws completos; medias móviles intermedias en 4h capturan los swings del rango antes del retroceso.
- Cómo probarla: Simular estrategia de tendencia en 4h (fast 20, slow 80) frente a las configuraciones fallidas de 1d en los 10 pares.

### Resiliencia del cruce EMA con RSI en 4h
- Fecha: 2026-10-30 05:27 UTC · Estado: pendiente
- Por qué: El sistema EMA 21/89 + RSI en 4h mantiene un Profit Factor de 1.56 a 3.42 en el torneo en vivo a pesar del entorno de rango.
- Cómo probarla: Probar en paper trading la variante con gestión de riesgo ATR (stop 2.0 / tp 4.0) en temporalidad 4h.

### Reversión a la media en 1h durante picos de volatilidad
- Fecha: 2026-10-30 05:27 UTC · Estado: pendiente
- Por qué: En rangos de alta volatilidad, las lecturas extremas de RSI en 1h ofrecen puntos de entrada con mejor payoff que en 15m.
- Cómo probarla: Evaluar la estrategia de reversión en 1h con rsi_low en 25 y un objetivo tp_atr amplio de 3.5.

### Filtro RSI en cruce EMA 21/89 mitiga falsas entradas en rango
- Fecha: 2026-10-30 09:27 UTC · Estado: pendiente
- Por qué: La estrategia EMA 21/89 + RSI en 4h mantiene win rate de 50-66% y PF positivo en el ranking vivo mientras el resto cae.
- Cómo probarla: Testear la familia ema_rsi en 4h con parámetros simétricos y amplio profit target de ATR.

### Canales Donchian amplios (80+ periodos) reducen choques por volatilidad
- Fecha: 2026-10-30 09:27 UTC · Estado: pendiente
- Por qué: Los canales de 20 a 30 periodos generaron pérdidas masivas (PF 0.32), requiriendo ventanas más amplias para filtrar el ruido.
- Cómo probarla: Evaluar la familia donchian en 1h usando un canal n=80 y ratio de beneficio/riesgo superior a 2:1.

### Resiliencia de EMA con filtro RSI en marcos de 4h
- Fecha: 2026-10-30 13:27 UTC · Estado: pendiente
- Por qué: El modelo live 'EMA 21/89 + RSI' es de los pocos con profit factor positivo (1.56 a 3.42), filtrando el ruido intradiario del régimen de rango.
- Cómo probarla: Evaluar la familia ema_rsi en 4h con medias 21/89 y un ratio riesgo-beneficio asimétrico stop 2.5 ATR / tp 5.0 ATR.

### Incremento de frecuencia en reversión para evitar descalificación
- Fecha: 2026-10-30 13:27 UTC · Estado: pendiente
- Por qué: Las reversiones previas con RSI 20 y 25 fallaron por generar 4 y 7 trades; relajar el gatillo a 32 permite capturar sobreventa en rangos volátiles con tamaño de muestra estadísticamente válido.
- Cómo probarla: Testear reversión en 1h con rsi_low en 32 y targets controlados de 1.8 ATR stop y 2.5 ATR tp.

### Eficiencia del marco de 4h sobre 1d en régimen de alta volatilidad
- Fecha: 2026-10-30 17:27 UTC · Estado: pendiente
- Por qué: Las tendencias diarias sufren drilldowns prolongados por giros bruscos, mientras que el marco de 4h captura el impulso intermedio antes del agotamiento.
- Cómo probarla: Evaluar el Profit Factor y Expectancy R comparativo de cruces EMA en 4h vs 1d durante los últimos 90 días en pares de vol alta.

### Captura de rupturas Donchian en 4h con expansiones de ATR
- Fecha: 2026-10-30 17:27 UTC · Estado: pendiente
- Por qué: Las rupturas en 1h sufrieron por ruido, pero en 4h filtran falsos quiebres en entornos de volumen y volatilidad elevada.
- Cómo probarla: Backtest de canales Donchian n=40 en 4h combinados con un filtro de salida por ATR adaptativo.

### Filtro RSI en 4h reduce entradas falsas en rangos volátiles
- Fecha: 2026-10-30 21:27 UTC · Estado: pendiente
- Por qué: El modelo EMA 21/89 + RSI en 4h es la única estrategia con PF positivo (1.56) en el entorno actual gracias al filtrado dinámico.
- Cómo probarla: Evaluar ema_rsi con temporización 4h, media rápida corta y ratio TP/SL superior a 1.5 en el dataset de entrenamiento.

### Reversión extrema en 15m supera al marco de 1h
- Fecha: 2026-10-30 21:27 UTC · Estado: pendiente
- Por qué: Las pruebas anteriores de reversión en 1h fallaron por escasez de operaciones o PF bajo; acortar a 15m busca capturar rebotes en la parte baja del rango intradía.
- Cómo probarla: Configurar rsi_low en 20 con temporización 15m y un stop amplio de ATR para soportar la volatilidad.

### Filtros de temporalidad diaria reducen latigazos en rango de alta volatilidad
- Fecha: 2026-10-31 01:27 UTC · Estado: pendiente
- Por qué: Las medias móviles en temporalidad diaria (1d) amortiguan el ruido intradía y las falsas rupturas en consolidaciones anchas.
- Cómo probarla: Evaluar la familia tendencia en 1d con combinación EMA 50/200 sobre el conjunto de entrenamiento.

### Reversión a la media con RSI extremo aprovecha expansiones de volatilidad
- Fecha: 2026-10-31 01:27 UTC · Estado: pendiente
- Por qué: En regímenes de rango y alta volatilidad, las sobreventas profundas generan rebotes técnicos de alta probabilidad y rápido recorrido.
- Cómo probarla: Probar la familia reversión en 1h con rsi_low en 25 y salidas dinámicas por ATR.

### Aceleración de Momentum en temporalidad alta
- Fecha: 2026-10-31 05:27 UTC · Estado: pendiente
- Por qué: El único éxito reciente proviene de familias de momentum en 1d, aprovechando activos con inercia alcista fuerte como BNB o ADA.
- Cómo probarla: Configurar una estrategia de momentum en marco temporal diario con lookback moderado y validar en backtest estricto.

### Filtro de volatilidad en Donchian
- Fecha: 2026-10-31 05:27 UTC · Estado: pendiente
- Por qué: Las rupturas directas de Donchian fallan por la alta tasa de whipsaws en mercados de rango.
- Cómo probarla: Aumentar los umbrales de stop ATR y tp ATR en la familia donchian para permitir mayor espacio de respiración a los trades.

### Optimización de Ema-Rsi en 4h
- Fecha: 2026-10-31 05:27 UTC · Estado: pendiente
- Por qué: Combinar cruces de medias con niveles de RSI permite capturar rebotes dentro de tendencias secundarias.
- Cómo probarla: Probar combinaciones con periodos rápidos más amplios y stops ajustados en marcos de 4h.

### Reversión rápida en marcos de 15m bajo volatilidad alta
- Fecha: 2026-10-31 09:27 UTC · Estado: pendiente
- Por qué: Los activos en rango y alta volatilidad tienden a sobreextenderse en soportes locales antes de rebotar.
- Cómo probarla: Implementar familia reversion en 15m con rsi_low en 25 y evaluar en papel durante 48 horas.

### Momentum de corto plazo en activos con alta beta
- Fecha: 2026-10-31 09:27 UTC · Estado: pendiente
- Por qué: Los rebotes en altcoins seleccionadas superan el rendimiento del mercado general cuando superan umbrales de retorno moderados.
- Cómo probarla: Probar familia momentum en 4h con lookback de 12 y min_ret de 0.03.

### Estrategia EMA/RSI en 1h para captura de tramos intermedios
- Fecha: 2026-10-31 09:27 UTC · Estado: pendiente
- Por qué: Permite filtrar falsas rupturas de rango utilizando medias rápidas combinadas con sobreventa.
- Cómo probarla: Validar en backtest interno la familia ema_rsi en 1h con fast 12 y slow 50.

### Filtro de momentum diario en activos con alta volatilidad
- Fecha: 2026-10-31 13:27 UTC · Estado: pendiente
- Por qué: Las estrategias basadas en momentum en marco diario muestran mayor resiliencia frente a los falsos rompimientos de marcos cortos.
- Cómo probarla: Validar la familia momentum con lookback medio y min_ret positivo en el conjunto de validación.

### Ampliación de umbrales en tendencia de 1d
- Fecha: 2026-10-31 13:27 UTC · Estado: pendiente
- Por qué: Las medias móviles rápidas generan demasiadas señales falsas en mercados laterales actuales.
- Cómo probarla: Probar medias móviles más lentas (fast > 50, slow > 150) en temporalidad diaria para filtrar ruido.

### Optimización de tendencia en marcos diarios amplios
- Fecha: 2026-10-31 17:27 UTC · Estado: pendiente
- Por qué: Las medias rápidas inferiores a 30 generan señales falsas en mercados laterales; se requiere mayor separación temporal.
- Cómo probarla: Validar la familia tendencia en 1d con fast=50 y slow=200 para filtrar ruido lateral.

### Momentum estricto para activos en tendencia
- Fecha: 2026-10-31 17:27 UTC · Estado: pendiente
- Por qué: Los activos con comportamiento direccional como NEAR y ZEC responden mejor a umbrales de retorno mínimo elevados.
- Cómo probarla: Desplegar momentum en 4h con lookback extendido y min_ret superior al 5%.

### Eficiencia de swing en 4h frente al ruido intradiario y el retraso diario
- Fecha: 2026-10-31 21:29 UTC · Estado: pendiente
- Por qué: El modelo EMA 21/89 + RSI en 4h ha demostrado ser el único ganador consistente porque filtra el ruido de 15m/1h y reacciona más rápido que las medias en 1d ante rangos prolongados.
- Cómo probarla: Validar una configuración formal de ema_rsi en 4h con ratios de riesgo/beneficio asimétricos (TP 5.0 ATR vs SL 2.5 ATR).

### Reversión a la media con umbral RSI ampliado para resolver falta de trades
- Fecha: 2026-10-31 21:29 UTC · Estado: pendiente
- Por qué: Un RSI de 20 generó solo 2 trades en entrenamiento; relajar el gatillo a RSI 30 en 1h aumentará la muestra manteniendo margen frente a comisiones spot.
- Cómo probarla: Evaluar reversion en 1h con rsi_low en 30 y TP superior a 2 ATR para compensar el spread y comisiones.

### Filtro de régimen para rupturas Donchian
- Fecha: 2026-11-01 01:29 UTC · Estado: pendiente
- Por qué: Las rupturas fallan sistemáticamente porque la mayoría de los activos se encuentran en regímenes de rango y baja volatilidad.
- Cómo probarla: Añadir un filtro de volatilidad o ADX mínimo antes de permitir entradas en las estrategias Donchian en marcos de 1h y 4h.

### Optimización del ratio de beneficio en EMA/RSI
- Fecha: 2026-11-01 01:29 UTC · Estado: pendiente
- Por qué: Las combinaciones de medias rápidas muestran mejor retención de expectativa matemática cuando se combinan con osciladores en 4h.
- Cómo probarla: Elevar ligeramente los objetivos de take profit mediante ATR y acotar el stop loss para mejorar el payoff.

### Optimización de Reversión en Cortos Plazos
- Fecha: 2026-11-01 05:29 UTC · Estado: pendiente
- Por qué: La mayoría de los activos se encuentran en rangos de volatilidad baja, lo que favorece la vuelta a la media en marcos de 1h frente a las rupturas tendenciales.
- Cómo probarla: Implementar configuraciones de reversion con RSI bajo en marcos de 1h con stops y take profits ajustados por ATR.

### Filtro de Momentum en Marcos de 4h
- Fecha: 2026-11-01 05:29 UTC · Estado: pendiente
- Por qué: El éxito parcial de la estrategia EMA + RSI en 4h indica que combinar la dirección de la EMA con un filtro de momentum captura mejor los movimientos limpios.
- Cómo probarla: Probar la familia de momentum y ema_rsi en marcos de 4h ajustando los umbrales de entrada para evitar falsas señales.

### Canales Donchian de Menor Duración
- Fecha: 2026-11-01 05:29 UTC · Estado: pendiente
- Por qué: Los canales Donchian largos fallan por la naturaleza lateral del mercado actual; periodos más cortos y stops estrictos pueden capturar impulsos locales.
- Cómo probarla: Evaluar la familia donchian con un lookback menor en 1h y 4h con un ratio de stop y tp simétrico.

### Mayor horizonte temporal filtra el ruido de baja volatilidad
- Fecha: 2026-11-01 09:29 UTC · Estado: pendiente
- Por qué: Las estrategias de 4h y 1d absorben mejor el costo del fee de 0.10% y evitan falsas rupturas dentro del rango actual.
- Cómo probarla: Evaluar parámetros de momentum diario (tf='1d', lookback=20) comparando su Profit Factor frente a 4h.

### Ampliación de canal Donchian para mitigar falsos breakouts
- Fecha: 2026-11-01 09:29 UTC · Estado: pendiente
- Por qué: Un canal Donchian de período largo (n=60 en 4h) captura solo impulsos estructurales reales, ignorando variaciones de baja volatilidad.
- Cómo probarla: Correr backtest de donchian 4h con n=60, stop_atr=2.5 y tp_atr=5.0 en los activos de mayor volatilidad relativa.

### Filtro de temporalidad 4h para tendencia
- Fecha: 2026-11-01 13:38 UTC · Estado: pendiente
- Por qué: Las tendencias en 1d reaccionan demasiado tarde al rango actual mientras que 1h produce señales falsas; 4h equilibra la duración de trade (~40h) observada en perfiles ganadores.
- Cómo probarla: Evaluar cruce EMA en 4h con parámetros de suavizado medio (25/100) en activos con volumen como BTC y ETH.

### Extremos de sobreventa en marcos intradiarios
- Fecha: 2026-11-01 13:38 UTC · Estado: pendiente
- Por qué: En rangos de baja volatilidad, las reversiones solo superan el umbral de tarifas si el RSI baja a niveles extremos (<25) con ratio beneficio/riesgo mayor a 1.5.
- Cómo probarla: Backtest de RSI < 20 en 15m con stop_atr holgado de 2.0 y objetivo de 3.0 ATR.
