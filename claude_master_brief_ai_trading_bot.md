# Brief maestro para Claude — Bot de Trading Autónomo con IA + UI de Control en Tiempo Real

Fecha: 2026-10-07

## 0. Propósito de este documento

Este documento NO pretende pedirte que clones las tres referencias visuales que acompañan este brief. Quiero que extraigas de ellas el enfoque de producto, observabilidad, jerarquía de información y lenguaje visual, y que lo apliques de forma superior a un bot de trading que ya existe.

IMPORTANTE: antes de modificar el bot existente, primero debes inspeccionarlo completamente. No asumas su arquitectura, stack, endpoints, modelos, base de datos, variables de entorno ni estado actual. No reemplaces componentes funcionales simplemente porque tu arquitectura preferida sea diferente.

El objetivo es construir un sistema de trading de criptomonedas orientado a investigación y experimentación, con paper trading/shadow mode como primera etapa y live trading únicamente cuando existan suficientes controles y validaciones.

La filosofía central es:

> El LLM no debe ser el bot. Debe ser un analista dentro de un sistema de decisión observable, medible, restringido por riesgo y auditable.

---

# 1. Referencias visuales: qué quiero conservar conceptualmente

Las tres referencias muestran tres perspectivas complementarias.

## Vista A — Performance / Equity Curve

La primera referencia presenta una curva intradía de capital con eje temporal, ganancias en verde, pérdidas en rojo y marcadores vinculados a las operaciones. Debajo aparece el listado cronológico de operaciones con activo, dirección, apertura, cierre y resultado.

Quiero conservar este concepto porque permite responder inmediatamente:

- ¿Cuánto dinero ganó o perdió el sistema?
- ¿En qué momento ocurrió?
- ¿Qué operaciones causaron el movimiento?
- ¿Cuánto tardó en recuperarse de una pérdida?
- ¿La estrategia tiene una distribución saludable de resultados?
- ¿Qué activos y direcciones están funcionando?

La futura UI debe mejorar esto con:

- equity curve;
- balance real;
- unrealized PnL;
- realized PnL;
- drawdown;
- peak-to-trough drawdown;
- fees;
- slippage;
- funding;
- exposición;
- número de posiciones;
- win rate;
- expectancy;
- profit factor;
- Sharpe/Sortino cuando la muestra sea suficiente;
- R múltiple;
- duración media de operaciones;
- long vs short;
- PnL por activo;
- PnL por régimen de mercado.

Cada operación debe ser seleccionable y llevar al usuario a su timeline de decisión.

---

# 2. Vista B — Control room / flujo de inteligencia

La segunda referencia es la más importante para la dirección del producto.

Tiene un canvas de nodos que representa cómo fluye la información:

Exchange → Mercado / Datos → indicadores y fuentes externas → filtro → controles → Analista IA → Motor de riesgo → Ejecución → Posición.

Quiero una versión mucho más profunda.

La pantalla principal debe permitir observar en vivo:

1. qué datos están entrando;
2. qué datos están actualizados;
3. qué datos están retrasados;
4. qué features se están calculando;
5. qué candidatos existen;
6. cuáles fueron filtrados;
7. por qué fueron filtrados;
8. qué candidatos llegaron al analista IA;
9. qué contexto recibió el analista;
10. qué decisión produjo;
11. qué política de riesgo modificó o bloqueó;
12. qué orden se generó;
13. qué ocurrió con la ejecución;
14. cuál es la posición resultante;
15. qué aprendió posteriormente el sistema.

No quiero un diagrama meramente decorativo.

Cada nodo debe representar un componente real o una etapa real del pipeline.

Cada conexión debe poder representar un evento real.

Cada evento importante debe poder tener:

- timestamp;
- fuente;
- latencia;
- estado;
- payload resumido;
- ID de correlación;
- versión del modelo;
- versión de estrategia;
- resultado.

---

# 3. Vista C — Learning / Memory

La tercera referencia introduce una idea que quiero llevar mucho más lejos.

Debe existir una diferencia estricta entre:

### Hipótesis

Algo que el sistema sospecha.

Ejemplo:

"Cuando funding está extremadamente positivo y el open interest aumenta rápidamente durante una subida parabólica, el riesgo de reversión parece aumentar."

Esto NO se convierte automáticamente en una regla.

Debe registrar:

- hipótesis;
- datos que la originaron;
- cantidad de casos;
- casos favorables;
- casos desfavorables;
- confianza;
- período observado;
- activos afectados;
- régimen de mercado;
- estado: propuesta / en evaluación / confirmada / refutada;
- versión de la hipótesis.

### Conocimiento confirmado

Una hipótesis solamente puede convertirse en conocimiento operativo después de superar criterios estadísticos definidos.

Debe conservar:

- evidencia;
- muestra;
- intervalo de confianza cuando sea aplicable;
- condiciones bajo las que funciona;
- condiciones bajo las que falla;
- fecha de validación;
- versión;
- impacto observado;
- posibilidad de rollback.

NO quiero "machine learning mágico".

Quiero memoria auditable.

---

# 4. Objetivo funcional del bot

El bot debe analizar múltiples criptomonedas y operar long y short cuando el exchange y el instrumento lo permitan.

Debe soportar cualquier activo disponible que cumpla requisitos mínimos de liquidez, pero inicialmente debe priorizar activos grandes y líquidos.

La configuración inicial recomendada debe poder ser:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- BNBUSDT
- XRPUSDT
- DOGEUSDT
- ADAUSDT
- AVAXUSDT
- LINKUSDT
- LTCUSDT
- y posteriormente ampliar dinámicamente.

El par de cotización debe ser configurable. USDT es una buena opción inicial si el exchange elegido tiene profundidad suficiente.

No hardcodear una lista cerrada en la arquitectura.

Debe existir un universo dinámico de activos con filtros:

- volumen;
- spread;
- profundidad;
- volatilidad;
- disponibilidad del instrumento;
- volumen mínimo;
- liquidez;
- riesgo;
- funding;
- correlación;
- concentración de cartera.

---

# 5. Contexto completo para las decisiones

El sistema NO debe tomar decisiones únicamente basándose en RSI/MACD/medias móviles.

Debe intentar construir un contexto multidimensional.

## Mercado

- precio;
- OHLCV;
- tendencia;
- estructura de mercado;
- momentum;
- volumen;
- volatilidad;
- ATR;
- realized volatility;
- cambios de régimen;
- correlación con BTC;
- correlación entre activos.

## Microestructura

Cuando esté disponible:

- bid/ask;
- spread;
- order book;
- profundidad;
- imbalance;
- market orders;
- trade flow;
- volumen agresor;
- slippage estimado;
- liquidez cercana al precio;
- distancia hasta niveles de baja liquidez.

## Derivados

Cuando el exchange lo permita:

- funding;
- open interest;
- cambios de open interest;
- basis;
- liquidaciones;
- long/short ratios;
- volumen de futuros/perpetuos.

## Opciones

Cuando exista acceso razonable:

- implied volatility;
- put/call;
- skew;
- open interest;
- expiraciones relevantes;
- niveles de gamma si son obtenibles de forma fiable.

No inventar datos.

Si una fuente no está disponible, mostrar "no disponible" y degradar la decisión de forma controlada.

## Liquidez

Quiero distinguir entre:

1. liquidez del libro del exchange donde se ejecutará;
2. liquidez agregada;
3. liquidez de DEX/pools cuando sea relevante.

No asumir que una métrica de TVL equivale automáticamente a liquidez ejecutable.

## Noticias

Las noticias deben formar parte del contexto, pero no deben ser una fuente única de verdad.

El pipeline debe:

- obtener noticias;
- eliminar duplicados;
- agrupar artículos sobre el mismo evento;
- identificar activo/sector afectado;
- identificar timestamp;
- evaluar fuente;
- estimar relevancia;
- estimar sentimiento;
- detectar eventos macro;
- detectar contradicciones;
- evitar contar 20 copias de la misma noticia como 20 señales.

La noticia debe terminar convertida en una señal estructurada.

---

# 6. IA / Gemini

El analista IA puede utilizar Gemini como primera implementación.

La IA debe recibir un contexto estructurado y compacto, no miles de líneas de datos sin procesar.

Debe recibir algo equivalente a:

```json
{
  "asset": "BTCUSDT",
  "timestamp": "...",
  "market_regime": "...",
  "price_context": {},
  "technical_features": {},
  "volume": {},
  "volatility": {},
  "order_book": {},
  "derivatives": {},
  "liquidity": {},
  "news_context": {},
  "sentiment": {},
  "portfolio": {},
  "open_positions": [],
  "opportunity_cost": {},
  "risk_budget": {},
  "backtest_context": {},
  "recent_similar_setups": [],
  "system_constraints": {}
}
```

La respuesta del modelo debe ser estructurada.

No permitir que el LLM devuelva simplemente:

"Comprar BTC porque parece alcista."

Debe producir algo equivalente a:

```json
{
  "decision": "WAIT",
  "direction": "LONG",
  "confidence": 0.64,
  "setup_quality": 0.71,
  "risk_flags": [],
  "supporting_factors": [],
  "contradicting_factors": [],
  "invalidating_conditions": [],
  "time_horizon": "...",
  "suggested_entry_zone": {},
  "suggested_stop_zone": {},
  "suggested_take_profit_zone": {},
  "reason_codes": [],
  "required_next_check": "...",
  "data_quality": {}
}
```

IMPORTANTE:

La interfaz puede mostrar un resumen del razonamiento y los factores utilizados, pero NO depender de exponer una cadena privada de pensamiento del modelo.

La UI debe mostrar:

- decisión;
- factores a favor;
- factores en contra;
- datos clave;
- riesgos detectados;
- condiciones de invalidación;
- confianza;
- calidad del contexto;
- versión del modelo;
- timestamp;
- coste de la consulta.

---

# 7. Separar IA de ejecución

La arquitectura debe ser:

DATA → FEATURES → FILTER → AI ANALYST → RISK ENGINE → EXECUTION → POSITION → OUTCOME → LEARNING

El LLM no debe tener permisos directos e ilimitados para enviar órdenes.

El motor de riesgo debe poder decir:

"IA quiere abrir $500 de exposición; política permite $120."

Resultado:

"ORDER RESIZED / BLOCKED"

La UI debe mostrar claramente esa intervención.

---

# 8. Motor de riesgo

Debe ser un componente independiente.

Debe calcular:

- capital disponible;
- capital comprometido;
- exposición total;
- exposición por activo;
- exposición por dirección;
- riesgo por operación;
- stop distance;
- position size;
- leverage si aplica;
- expected loss;
- expected reward;
- R:R;
- portfolio correlation;
- max daily loss;
- max drawdown;
- max concurrent positions;
- max exposure;
- cooldown después de pérdidas;
- límites por activo;
- límites por volatilidad;
- límites por liquidez.

Debe poder rechazar una operación incluso si la IA quiere ejecutarla.

Ejemplos:

```text
AI: LONG BTC
Risk: BLOCKED
Reason: daily loss limit reached
```

o:

```text
AI: LONG ETH
Risk: RESIZED
Requested exposure: $400
Allowed exposure: $175
Reason: correlated BTC exposure
```

---

# 9. Coste de oportunidad

Quiero una capa específica de portfolio intelligence.

Antes de abrir una nueva posición, el sistema debería preguntarse:

- ¿Qué capital estoy utilizando?
- ¿Existe una posición abierta con mejor expectativa?
- ¿Cerrar parcialmente una posición libera capital para una oportunidad superior?
- ¿La nueva posición está altamente correlacionada con otra?
- ¿Estoy duplicando el mismo factor de riesgo?
- ¿La liquidez actual hace que la operación sea cara?
- ¿El beneficio esperado compensa fees + slippage + funding + riesgo?

Esto debe formar parte del contexto de decisión.

---

# 10. Backtesting y contexto histórico

No quiero que el LLM "haga backtesting" improvisando.

El sistema debe disponer de un motor de backtesting determinista.

Debe permitir:

- backtest por activo;
- backtest por estrategia;
- walk-forward;
- out-of-sample;
- diferentes regímenes;
- diferentes timeframes;
- fees;
- slippage;
- funding;
- latencia simulada cuando sea posible;
- ejecución parcial;
- liquidez limitada cuando sea modelable.

El LLM puede interpretar resultados.

No debe inventarlos.

La IA debe recibir resultados ya calculados.

---

# 11. Replay de decisiones

Una funcionalidad importante.

Cada decisión debe poder reproducirse.

Guardar:

- market snapshot;
- features;
- noticias disponibles en ese momento;
- order book snapshot/resumen;
- derivados;
- portfolio state;
- posiciones;
- riesgo;
- prompt estructurado/versionado;
- modelo;
- respuesta estructurada;
- decisión final;
- decisión del risk engine;
- orden;
- resultado posterior.

Luego poder abrir:

"BTCUSDT — 2026-10-07 14:32:11"

y reconstruir exactamente qué sabía el sistema en ese instante.

---

# 12. UI principal

Quiero una interfaz tipo "AI Trading Control Room".

No quiero un dashboard administrativo genérico.

Debe parecer una consola de inteligencia financiera.

## Header

Debe mostrar:

- estado del bot;
- modo actual;
- hora UTC;
- capital;
- PnL diario;
- PnL total;
- drawdown;
- operaciones abiertas;
- operaciones cerradas;
- consultas IA;
- coste IA;
- latencia;
- salud de fuentes.

Modos:

- OFFLINE
- PAPER
- SHADOW
- LIVE

También:

- SOLO CIERRE
- PAUSADO
- OPERANDO
- EMERGENCIA

## Control de agresividad

Debe existir un control claramente visible.

Pero debe mapearse a parámetros reales.

Ejemplo:

AGGRESSIVENESS 1–10

Puede afectar:

- umbral de entrada;
- máximo riesgo;
- número de posiciones;
- frecuencia de evaluación;
- tolerancia a volatilidad;
- R:R mínimo;
- exposición máxima.

Nunca debe ser simplemente un slider decorativo.

---

# 13. Canvas de nodos

Nodos principales:

EXCHANGE

MARKET DATA

ORDER BOOK

TRADES

DERIVATIVES

FUNDING

OPEN INTEREST

OPTIONS

DEX / LIQUIDITY

NEWS

MACRO

SENTIMENT

FEATURE ENGINE

REGIME DETECTOR

CANDIDATE FILTER

PORTFOLIO ANALYZER

AI ANALYST

RISK ENGINE

EXECUTION

POSITION

LEARNING

MEMORY

Cada nodo debe indicar:

- estado;
- latencia;
- último update;
- cantidad de datos;
- errores;
- fuente.

Estados:

- HEALTHY
- DEGRADED
- STALE
- ERROR
- DISABLED

---

# 14. Visualización de eventos en vivo

No quiero animación por animación.

Cuando un evento real ocurra:

```text
BTCUSDT
↓
New order book imbalance detected
↓
Candidate generated
↓
Filter passed
↓
AI evaluation started
↓
AI: WAIT
↓
No order
```

La línea debe mostrar actividad.

Si hay una orden:

```text
BTCUSDT
↓
Candidate
↓
AI LONG
↓
Risk check
↓
Position size = $145
↓
Order sent
↓
Order partially filled
↓
Position OPEN
```

La UI debe poder seguir ese recorrido.

---

# 15. Panel "Why?"

Para cada decisión:

"¿Por qué el bot hizo esto?"

Mostrar:

### Factores positivos
- tendencia;
- momentum;
- volumen;
- order book;
- funding;
- noticias;
- liquidez.

### Factores negativos
- volatilidad;
- spread;
- drawdown;
- correlación;
- riesgo macro;
- contradicción entre señales.

### Riesgo
- stop;
- pérdida máxima;
- exposición;
- R:R;
- portfolio impact.

### Decisión
- OPEN LONG
- OPEN SHORT
- HOLD
- WAIT
- REDUCE
- CLOSE

---

# 16. Operaciones

La pantalla de operaciones debe mostrar:

- símbolo;
- dirección;
- entrada;
- precio actual;
- stop;
- TP;
- cantidad;
- exposición;
- PnL;
- PnL %;
- fees;
- funding;
- duración;
- R;
- motivo;
- estado.

Al abrir una operación:

timeline:

```text
14:20:01 market snapshot
14:20:02 candidate created
14:20:03 AI analysis
14:20:04 risk approval
14:20:05 order submitted
14:20:06 partial fill
14:20:08 full fill
...
```

---

# 17. Aprendizaje

No permitir que el sistema se auto-modifique arbitrariamente.

El aprendizaje debe pasar por estados:

PROPOSED
→ TESTING
→ VALIDATED
→ ACTIVE
→ DEPRECATED
→ REJECTED

Una modificación de estrategia debe guardar:

- versión anterior;
- versión nueva;
- evidencia;
- backtest;
- walk-forward;
- resultados live/paper;
- fecha;
- motivo;
- rollback.

---

# 18. Fuentes y APIs

La prioridad es usar APIs gratuitas o muy económicas durante el experimento.

No quiero añadir servicios de pago innecesarios.

## Obligatorio

### Exchange

El exchange elegido será la fuente principal para:

- precios;
- trades;
- OHLCV;
- order book;
- balance;
- órdenes;
- fills;
- posiciones;
- funding;
- derivados, si están disponibles.

Se requerirá:

- API key;
- API secret;
- permisos de lectura;
- permisos de trading solamente cuando se pase a live;
- retiro/desembolso DESACTIVADO.

Nunca crear una key con permisos de retiro.

Para desarrollo:

- paper trading;
- sandbox/testnet si el exchange lo soporta;
- live read-only antes de live execution.

---

# 19. Gemini

Gemini será el proveedor inicial del analista IA.

La clave debe vivir únicamente en backend.

Variable:

```env
GEMINI_API_KEY=
GEMINI_MODEL=
```

No colocar la clave en frontend.

La integración debe tener:

- timeout;
- retries;
- rate limiting;
- circuit breaker;
- fallback;
- coste por consulta;
- token usage;
- cache;
- request ID;
- model version;
- prompt version.

A fecha de este documento, Google ofrece un nivel gratuito para determinados modelos y una capa de pago para mayor capacidad; los límites dependen del modelo y pueden cambiar. Consultar la documentación oficial antes de fijar un modelo definitivo.

---

# 20. Datos generales de mercado

CoinGecko puede servir como fuente secundaria y de enriquecimiento, no como fuente principal de ejecución.

Actualmente su Demo API ofrece acceso gratuito con límites de uso y atribución; es útil para desarrollo, metadatos, precios agregados e histórico, pero el sistema debe diseñarse para funcionar aunque esta fuente falle.

No depender de CoinGecko para decisiones de milisegundos.

---

# 21. Liquidez / DeFi

DefiLlama puede aportar datos de TVL, fees, revenue, volumen y otros indicadores DeFi.

Usarlo como contexto macro/DeFi, no como sustituto de la profundidad real del libro del exchange.

También se puede integrar una fuente de DEX/pools como DexScreener u otra alternativa, detrás de un adapter.

La arquitectura debe permitir sustituir el proveedor.

---

# 22. Fear & Greed

Alternative.me puede utilizarse como señal secundaria de sentimiento de mercado.

No utilizarla como trigger directo.

Debe convertirse en feature contextual.

---

# 23. Noticias

No asumir que "Google News API" es una API oficial pública equivalente a un proveedor de datos profesional.

Para el MVP evaluar:

1. RSS de Google News / fuentes RSS;
2. GNews;
3. NewsAPI;
4. proveedor premium solamente si posteriormente hace falta.

GNews ofrece actualmente un plan gratuito para desarrollo/testing con límites y retraso; no asumir que sirve para producción comercial sin revisar su licencia.

NewsAPI también tiene un Developer plan gratuito, pero actualmente está limitado a desarrollo/testing y sus datos del plan gratuito tienen retraso, por lo que no debe ser considerado fuente de noticias en tiempo real para live trading.

La arquitectura debe usar:

```text
NewsProvider
  ├── GNewsProvider
  ├── NewsApiProvider
  ├── RSSProvider
  └── FuturePremiumProvider
```

---

# 24. Google Search / grounding

Si Gemini puede utilizar grounding con búsqueda, evaluarlo como mecanismo complementario.

No convertirlo en dependencia crítica.

El sistema debe poder funcionar con:

- noticias almacenadas;
- fuentes RSS;
- proveedores de noticias;
- búsqueda opcional.

---

# 25. Variables de entorno

No pedir al usuario que pegue claves secretas en archivos de código.

Usar:

```env
EXCHANGE_API_KEY=
EXCHANGE_API_SECRET=

GEMINI_API_KEY=
GEMINI_MODEL=

NEWS_PROVIDER=
NEWS_API_KEY=

COINGECKO_API_KEY=

DATABASE_URL=

REDIS_URL=

VPS_HOST=
VPS_USER=
VPS_SSH_KEY_PATH=

BOT_MODE=paper
TRADING_ENABLED=false
WITHDRAWALS_ENABLED=false
```

No todas estas variables serán obligatorias.

Primero determinar qué integraciones son realmente necesarias.

NO inventar API keys que no se necesitan.

No enviar secretos al frontend.

No escribir secretos en logs.

No incluir secretos en commits.

---

# 26. Requisito especial sobre secretos

Aunque el experimento sea controlado, NO quiero que las claves queden escritas dentro del código fuente.

Si el usuario proporciona una clave, guardarla en el mecanismo de secretos/variables de entorno del entorno de ejecución.

Para live trading:

- trading permission explícito;
- withdrawals disabled;
- IP whitelist si el exchange la soporta;
- límite de capital;
- kill switch;
- solo cierre;
- emergency close.

---

# 27. Observabilidad

El bot debe tener logging estructurado.

Cada evento debe incluir:

- timestamp UTC;
- level;
- service;
- asset;
- correlation ID;
- event ID;
- strategy version;
- model version;
- mode;
- latency;
- result.

No registrar:

- API secrets;
- private keys;
- tokens completos;
- credenciales.

Métricas:

- decisions/min;
- data latency;
- AI latency;
- execution latency;
- API errors;
- rate limit usage;
- model cost;
- orders;
- fills;
- rejected orders;
- risk blocks;
- stale sources;
- PnL;
- drawdown.

---

# 28. Arquitectura propuesta

Usar una arquitectura modular con adapters.

Conceptualmente:

```text
                 ┌─────────────────┐
                 │ Exchange Adapter │
                 └────────┬────────┘
                          ↓
                 ┌─────────────────┐
                 │ Market Collector│
                 └────────┬────────┘
                          ↓
                 ┌─────────────────┐
                 │ Feature Engine  │
                 └────────┬────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
 Candidate Engine                      Portfolio
        ↓                                   ↓
        └────────────────┬──────────────────┘
                         ↓
                  ┌───────────────┐
                  │ AI Analyst    │
                  └───────┬───────┘
                          ↓
                  ┌───────────────┐
                  │ Risk Engine   │
                  └───────┬───────┘
                          ↓
                  ┌───────────────┐
                  │ Execution     │
                  └───────┬───────┘
                          ↓
                     Position
                          ↓
                     Outcome
                          ↓
                    Learning
                          ↓
                     Memory
```

La UI consume eventos y snapshots de estos módulos.

---

# 29. Persistencia

Se necesita almacenar como mínimo:

- market snapshots seleccionados;
- features;
- candidatos;
- decisiones;
- AI evaluations;
- risk decisions;
- orders;
- fills;
- positions;
- closed trades;
- news events;
- learning hypotheses;
- validated knowledge;
- strategy versions;
- prompt versions;
- model versions;
- system events.

Diseñar retención por niveles para evitar que almacenar cada tick indefinidamente sea innecesariamente caro.

---

# 30. Modos operativos

Debe existir un state machine explícito.

```text
OFFLINE
PAPER
SHADOW
LIVE
EMERGENCY
```

Y controles:

```text
TRADING ENABLED
CLOSE ONLY
PAUSED
KILL SWITCH
```

Nunca permitir una transición silenciosa de PAPER a LIVE.

---

# 31. Seguridad de ejecución

Antes de una orden:

```text
Candidate
↓
Strategy validation
↓
AI validation
↓
Risk validation
↓
Portfolio validation
↓
Execution validation
↓
Order
```

Después:

```text
Order
↓
Exchange acknowledgement
↓
Fill monitoring
↓
Position reconciliation
↓
Risk recalculation
```

El reconciliador debe comparar periódicamente:

BOT STATE vs EXCHANGE STATE.

Si divergen:

```text
RECONCILIATION ERROR
```

y bloquear nuevas entradas hasta resolver el estado.

---

# 32. Kill switch

Debe poder detener nuevas entradas inmediatamente.

Pero permitir:

- cancelar órdenes pendientes;
- cerrar posiciones;
- solo cierre;
- emergency close.

Debe existir un mecanismo independiente del LLM.

---

# 33. VPS

La aplicación se desplegará posteriormente en una VPS ya disponible.

No comenzar el despliegue hasta:

1. inspeccionar el repositorio;
2. identificar stack;
3. revisar Docker/servicios;
4. revisar variables de entorno;
5. ejecutar tests;
6. verificar paper mode;
7. comprobar health checks.

La información SSH debe mantenerse fuera del código.

No guardar claves privadas dentro del repositorio.

---

# 34. Roadmap

## Fase 0 — Auditoría

Antes de modificar:

- estructura del repo;
- frontend;
- backend;
- DB;
- configuración;
- dependencias;
- tests;
- integraciones;
- estrategia;
- execution engine;
- logs;
- seguridad.

Entregar primero un diagnóstico.

## Fase 1 — Data layer

Implementar:

- exchange adapter;
- market data;
- order book;
- trades;
- OHLCV;
- funding;
- open interest si existe;
- normalización;
- timestamps;
- health checks.

## Fase 2 — Feature engine

Implementar:

- indicadores;
- tendencia;
- volumen;
- volatilidad;
- microestructura;
- liquidez;
- régimen;
- correlaciones.

## Fase 3 — Candidate engine

Reducir el universo de activos.

Debe explicar:

```text
BTCUSDT — candidate score 82/100
ETHUSDT — candidate score 71/100
XRPUSDT — rejected: low liquidity
```

## Fase 4 — News/context engine

Integrar:

- RSS;
- proveedor de noticias;
- sentimiento;
- deduplicación;
- clasificación;
- eventos macro.

## Fase 5 — AI analyst

Integrar Gemini.

Primero:

```text
AI recommendation only
```

Sin ejecución.

## Fase 6 — Risk engine

Integrar:

- position sizing;
- max risk;
- portfolio constraints;
- exposure;
- drawdown;
- correlation;
- liquidity.

## Fase 7 — Paper trading

Operar virtualmente.

Generar estadísticas.

## Fase 8 — Replay + backtesting

Validar decisiones históricas.

## Fase 9 — Learning

Implementar hipótesis y conocimiento validado.

## Fase 10 — UI Control Room

Construir la interfaz completa.

## Fase 11 — Shadow trading

Comparar:

```text
what bot would have done
vs
what market actually did
```

## Fase 12 — Live con capital mínimo

Solo después de cumplir todos los gates de seguridad.

---

# 35. Reglas de diseño

No quiero:

- dashboard SaaS genérico;
- exceso de cards;
- gráficos sin propósito;
- neon excesivo;
- gradientes gratuitos;
- glassmorphism;
- animaciones decorativas;
- texto de IA inventado;
- "thinking" falso;
- números ficticios presentados como reales;
- métricas sin timestamp;
- estados falsos;
- botones que no tengan backend real.

Sí quiero:

- consola financiera;
- alta densidad informativa;
- jerarquía;
- precisión;
- estados reales;
- visualización en tiempo real;
- trazabilidad;
- replay;
- observabilidad;
- control humano;
- diseño compartible en pantalla.

---

# 36. Regla crítica para el desarrollo

No hagas cambios estructurales importantes antes de inspeccionar el bot existente.

Primero:

```text
READ
→ MAP
→ UNDERSTAND
→ REPORT
→ PLAN
→ IMPLEMENT
→ TEST
→ DEPLOY
```

No:

```text
GUESS
→ REWRITE
→ BREAK
```

Si una pieza existente funciona, conservarla.

Si necesita modificación, explicar:

- problema;
- causa;
- impacto;
- cambio propuesto;
- alternativa;
- riesgo;
- cómo probarlo.

---

# 37. Resultado final esperado

Quiero terminar con un producto que se pueda abrir en pantalla y entender en segundos:

```text
¿Está operando?
¿Con cuánto capital?
¿Cuánto está arriesgando?
¿Qué mercados está vigilando?
¿Qué está analizando?
¿Por qué no está entrando?
¿Por qué entró?
¿Qué datos utilizó?
¿Qué decidió Gemini?
¿Qué permitió/bloqueó Risk Engine?
¿Qué posición existe?
¿Qué está ocurriendo ahora?
¿Qué aprendió?
¿Qué fuentes están fallando?
¿Cuánto cuesta mantener la IA?
```

Y, al seleccionar una decisión:

```text
DECISION
↓
CONTEXT
↓
FEATURES
↓
AI ANALYSIS
↓
RISK
↓
EXECUTION
↓
OUTCOME
↓
LEARNING
```

Todo debe poder rastrearse.

---

# 38. Entregables que quiero de Claude antes de tocar código

1. Mapa completo del repositorio existente.
2. Arquitectura actual.
3. Inventario de integraciones.
4. Inventario de variables de entorno.
5. Inventario de riesgos.
6. Gap analysis contra este brief.
7. Arquitectura propuesta.
8. Roadmap por fases.
9. Lista exacta de nuevas dependencias.
10. Lista exacta de API keys realmente necesarias.
11. Coste estimado mensual en modo paper.
12. Coste estimado mensual en modo live.
13. Plan de seguridad.
14. Plan de observabilidad.
15. Plan de datos.
16. Plan de UI.
17. Plan de testing.
18. Plan de deployment.
19. Criterios de aceptación por fase.

NO empezar a implementar hasta presentar este diagnóstico y obtener aprobación.

---

# 39. API/key checklist inicial

No pedir todas las claves indiscriminadamente.

Primero identificar cuáles son realmente necesarias.

### Probablemente obligatorias

- Exchange API key.
- Exchange API secret.

### Probablemente necesaria

- Gemini API key.

### Opcionales

- GNews API key.
- NewsAPI key.
- CoinGecko API key.

### Posiblemente innecesarias

- DefiLlama, dependiendo del endpoint y del volumen.
- Alternative.me.
- RSS público.

### Condicionales

- Etherscan/Block explorer.
- Alchemy/QuickNode.
- proveedores de opciones.
- proveedor premium de noticias.
- proveedor de social sentiment.

La respuesta debe distinguir:

```text
NECESARIA
RECOMENDADA
OPCIONAL
NO NECESARIA
```

No pedir una clave si la integración puede funcionar razonablemente sin ella.

---

# 40. Nota de seguridad sobre claves

Aunque el experimento sea temporal, no quiero secretos dentro del código fuente.

Preferir:

- `.env`;
- secret manager;
- Docker secrets;
- variables de entorno de la VPS;
- permisos de archivo restrictivos.

Si el usuario proporciona una clave por chat, tratarla como secreto comprometible y recomendar revocarla/rotarla al terminar el experimento.

Nunca imprimir el valor completo en logs, UI, commits o respuestas.

---

# 41. Principio final

Construye un sistema de trading observable, experimental y auditable.

No quiero una "IA que compra y vende".

Quiero un:

**AI Trading Intelligence System**

capaz de observar:

```text
MARKET
LIQUIDITY
MICROSTRUCTURE
DERIVATIVES
NEWS
MACRO
SENTIMENT
PORTFOLIO
HISTORY
```

razonar mediante componentes separados:

```text
FEATURES
FILTER
AI
RISK
EXECUTION
```

y aprender mediante:

```text
OUTCOME
→ HYPOTHESIS
→ TEST
→ VALIDATION
→ MEMORY
```

La UI debe convertir todo ese proceso en una representación visual en vivo, entendible y auditable.

No clones las referencias.

Toma su idea central y llévala a un nivel de producto superior.
