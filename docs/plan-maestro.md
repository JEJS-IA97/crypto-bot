# Plan maestro crypto-bot — continuidad entre chats

Actualizado 2026-10-09 · Repo: https://github.com/JEJS-IA97/crypto-bot (rama master) · Método y skills: https://github.com/JEJS-IA97/silex

> Aviso: no soy asesor financiero y ningún bot puede garantizar que no se pierda dinero. Este plan busca limitar pérdidas y exigir evidencia antes de arriesgar capital real.

## 1. Veredicto en 30 segundos

- La base es seria: backend FastAPI + panel React, 10 specs con método SDD, constitución de 13 reglas, simulación → testnet → real con compuertas, kill switch, riesgo por operación y por día, auditoría de decisiones.
- Hoy el bot hace una sola cosa: estrategia ORB (ruptura del rango de apertura de Nueva York) en Binance Spot, solo compras, capital de 20 USD. Todavía NO hace copy trading, NO opera en BingX/OKX y NO aprende solo.
- Tu visión (multi-exchange + copy trading + IA que aprende) choca con 3 reglas actuales de la constitución. No es un bloqueo técnico: es una decisión tuya que hay que registrar en una spec nueva (ver sección 5).
- Recomendación: terminar la spec 010 en curso, luego construir evidencia (backtest walk-forward + paper) y recién después abrir exchanges y copy trading, primero en modo sombra (sin dinero).

## 2. Estado real del repo (verificado clonando y ejecutando)

| Área | Estado |
| --- | --- |
| Specs 001–009 | Completas (todas las casillas de tasks.md marcadas): bot Binance Spot, nube + informe diario, panel, informe HTML, observabilidad, contexto de datos, analista IA Gemini (solo recomienda), motor de riesgo v2, Control Room |
| Spec 010 Learning | T1 y T2 hechas; T3–T7 pendientes (evaluación estadística, knowledge, strategy\_versions, API, pestaña Learning, validación) |
| Backend | \~13.300 líneas en app/, ruff limpio |
| Tests backend | 488 ejecutados: 10 fallos + 3 errores. Casi todos son el rojo intencional de la spec 010 (TDD: tests escritos antes del código). Uno aparte: test\_frozen\_zone reporta 3 archivos congelados modificados (arbitrage\_service, trade\_opportunity\_service, market\_sync\_service); sospecha: diferencia de saltos de línea/entorno entre Windows y Linux, NO verificado |
| Entorno | El proyecto declara Python 3.14; mi verificación corrió en Python 3.12 |
| Estrategia | ORB 9:00–10:00 NY, TP y SL de 2%, 4 pares ORB (BTC, ETH, BNB, SOL), 8 pares monitoreados |
| Riesgo | Máx. 1 USD de pérdida por operación, pérdida diaria ≤5%, 3 posiciones, exposición ≤75% del capital aportado, circuit breaker, kill switch |
| Fases y compuertas | SIMULATION → TESTNET → LIVE; para avanzar: ≥30 días de paper, ≥15 operaciones, PnL>0, drawdown ≤10%; real exige ALLOW\_LIVE\_TRADING=true |
| IA | Gemini como analista bajo demanda (≤4 consultas/día), solo recomendación, nunca ejecuta |
| Copy trading | Solo existe un formulario/webhook de señales externas con TTL y anti-duplicados. No hay descubrimiento ni seguimiento de traders |
| OKX y arbitraje | Código legado congelado por la constitución (RF-21), no operativo |
| Despliegue | Render free + Neon Postgres + GitHub Pages + GitHub Actions (informe diario por correo) |
| Pendiente operativo | APPLY.md: aplicar el fix del colector de snapshots y recolectar datos (6 h de BTC/ETH/SOL) |

## 3. Brechas frente a lo que quieres

| Quieres | Realidad hoy | Qué hay que hacer |
| --- | --- | --- |
| Binance + BingX + OKX | Solo Binance Spot; OKX congelado; BingX no existe | Capa de adaptadores por exchange (spec nueva) + cambiar constitución #1 |
| Copy trading | No existe | Módulo de descubrimiento/puntuación/seguimiento en modo sombra primero |
| Mejores estrategias del mercado | 1 estrategia (ORB) + señal EMA/RSI en dominio | Portafolio de 2–3 estrategias evaluadas con walk-forward |
| Que aprenda solo | Spec 010 = hipótesis con activación manual; la constitución prohíbe auto-modificación | Definir nivel de autonomía permitido (sección 4.3) |
| No perder dinero | Controles de pérdida buenos, pero sin evidencia de rentabilidad todavía | Gates de evidencia + tope de capital + breaker global |
| Pasivo 24/7 | Render free se duerme (hay keepalive) | VPS pequeño antes de LIVE |

## 4. Investigación y ajustes recomendados

### 4.1 Copy trading: lo que encontré

- OKX documenta endpoints de copy trading, incluyendo ranking público de lead traders, estadísticas de lead trader, historial de posiciones del lead y lista de traders que sigues. También tiene filtro de traders API (exige que ≥80% de los últimos 30 días hayan sido por API). Es el candidato más viable para automatizar el descubrimiento.
- Binance: la documentación oficial de Copy Trading lista endpoints del lado del lead trader (estado de lead y lista blanca de símbolos). No encontré un endpoint oficial para que un seguidor explore ranking y siga traders desde su API; el seguimiento se hace en la app. A verificar en la spec.
- BingX: descontinuó en diciembre de 2024 el copy trading enlazando API de Binance. Tiene su propio copy trading dentro de la plataforma; no verifiqué si expone API para seguidores.
- Casi todo el copy trading nativo es de futuros; tu constitución fase 1 prohíbe futuros, margen y apalancamiento. Spot copy existe en OKX y Binance, con menos oferta.
- La disponibilidad del copy trading depende del país y de tu cuenta: verifícalo antes de planear sobre él.

### 4.2 Evidencia sobre seguir traders (importante para tu objetivo de no perder)

- Un estudio de más de 100.000 resultados en Binance, Bybit y MEXC (publicado en el blog de KuCoin, fuente con interés comercial) reporta que el 97% de los lead traders ganaba para sí mismos pero solo \~43,6% generaba ganancias a sus seguidores. Tómalo como indicio, no como verdad exacta.
- Los rankings sufren sesgo de supervivencia: muestran a quien sigue vivo y suele ganar quien más riesgo tomó. Un estudio experimental (Apesteguia, Oechssler y Weidenholzer, Management Science 2020) concluye que copiar induce a asumir más riesgo.
- Criterios de selección razonables: historial largo (meses, no semanas), relación retorno/drawdown máximo ≥ 2, tamaño de posición estable, sin picos de una sola operación, y preferencia por traders que operan por API (más sistemáticos).
- Reglas de gestión al copiar: repartir entre varios traders, tope por trader (por ejemplo 10% del capital) y salida automática si el trader supera su drawdown histórico.

### 4.3 Aprendizaje automático: niveles posibles

| Nivel | Qué hace | Riesgo | Recomendación |
| --- | --- | --- | --- |
| L0 (spec 010) | Hipótesis estadísticas; tú activas todo | Muy bajo | Terminar ahora |
| L1 | Búsqueda de parámetros con walk-forward offline; propone strategy\_versions que tú apruebas | Bajo | Siguiente |
| L2 | Meta-asignador (por ejemplo bandit o pesos por Sharpe móvil) que reparte capital entre estrategias o traders YA aprobados, con topes duros | Medio | Primero en modo sombra; exige enmienda de constitución |
| L3 | Reinforcement learning en vivo con dinero | Alto: sobreajuste, mercado no estacionario | No recomendado |

Por qué: los mercados cambian de régimen, y un modelo que aprende de pocas operaciones con 20 USD se sobreajusta al ruido. La constitución #9 ya exige split temporal sin look-ahead y métricas; se mantiene.

### 4.4 Riesgo adicional recomendado

- Breaker global de portafolio: si el equity cae X% desde su máximo, pasar a CLOSE-ONLY y avisar.
- Topes por exchange y por trader copiado; correlación entre posiciones.
- Reconciliación periódica bot ↔ exchange (hoy el diagnóstico la marca como pendiente).
- Claves API: sin permiso de retiro, lista blanca de IP, rotación documentada; claves solo en backend.
- Costos: con 20 USD las comisiones (0,1% por lado en Binance Spot) y mínimos de orden dominan; el valor de esta etapa es validar el sistema, no ganar dinero.

### 4.5 Infraestructura

Render free sirve para paper. Para operar 24/7 sin estar pendiente, mover a un VPS pequeño antes de LIVE (el brief original ya lo prevé en su §33), con alertas por correo/Telegram.

## 5. Decisiones que necesito de ti

| # | Decisión | Mi recomendación |
| --- | --- | --- |
| D-1 | Enmendar constitución #1 para construir y simular OKX y BingX (sin dinero real) | Sí, solo simulación/demo; real sigue siendo solo Binance Spot |
| D-2 | Copy trading: ¿sombra primero (registrar lo que habrías copiado) o directo con dinero? | Sombra mínimo 30 días |
| D-3 | ¿Se permite futuros/copy de futuros algún día? | No hasta tener evidencia en spot; exigiría nueva constitución |
| D-4 | Autonomía de aprendizaje | L1 ahora, L2 en sombra; nunca L3 |
| D-5 | Capital real inicial y reparto entre exchanges | Mantener 20 USD solo en Binance hasta pasar gates |
| D-6 | Hosting para operación continua | VPS pequeño antes de LIVE |

## 6. Plan por fases (cada fase = una spec; flujo SDD de 7 pasos de silex; se detiene para tu aprobación entre fases)

### Fase A — Cerrar lo abierto (ahora)

1. Spec 010 T3: evaluate\_hypothesis (RF-2). Hecho cuando: test\_learning\_evaluate en verde, suite completa sin regresiones.
2. T4: knowledge + strategy\_versions + API /api/learning/\*; suite backend completa en verde.
3. T5–T6: tests y UI de la pestaña Learning.
4. T7: validación final (ruff, compileall, unittest, npm lint y npm test).
5. Investigar el test\_frozen\_zone en el entorno real del proyecto (¿saltos de línea CRLF?) y arreglarlo sin tocar los archivos congelados.
6. Aplicar APPLY.md (fix del colector) y lanzar la recolección de datos.

### Fase B — Spec 011: evidencia (backtest walk-forward + métricas)

Tareas: dataset histórico de klines multi-par; walk-forward con ventanas rodantes; comisiones, slippage y fills realistas; métricas (retorno, drawdown, Sharpe, profit factor, expectancy); reporte comparativo. Hecho cuando: ORB tiene veredicto con datos fuera de muestra. Gate: si ninguna estrategia supera comisiones fuera de muestra, no se avanza a dinero real.

### Fase C — Spec 012: capa de exchanges (requiere D-1)

Interfaz única de adaptador (precios, balance, órdenes, estado) con implementaciones Binance (existente), OKX (reactivar el cliente demo con spec nueva) y BingX (nuevo, mejor vía su modo demo si existe: a verificar). Todo con httpx mockeado en tests, nada de red en tests (constitución #11). Gate: paper y demo/testnet funcionando en los tres; real sigue bloqueado.

### Fase D — Spec 013: portafolio de estrategias

2–3 estrategias con lógica distinta (por ejemplo ruptura ORB, tendencia con EMA/RSI que ya existe en el dominio, reversión a la media en rango) más detector de régimen (volatilidad y fuerza de tendencia). Cada una entra solo con métricas walk-forward. Gate: portafolio con drawdown simulado ≤10% y PnL>0 fuera de muestra.

### Fase E — Spec 014: copy trading en modo sombra

Descubrimiento (empezar por OKX: ranking público + stats), puntuación por criterios de 4.2, selección de N traders, registro de lo que habrías copiado y su resultado real simulado con comisiones y retraso. Reglas: tope por trader, salida si supera su drawdown histórico. Sin dinero. Gate: ≥30 días de sombra con resultado neto positivo después de costos.

### Fase F — Spec 015: aprendizaje L1/L2

L1: propuestas de parámetros vía walk-forward registradas en strategy\_versions. L2 en sombra: asignador de pesos entre estrategias/traders aprobados con topes. Requiere enmienda de la constitución definida con D-4.

### Fase G — Spec 016: operación 24/7

VPS, alertas, reconciliación, breaker global, rotación de claves, checklist de LIVE (docs/checklist.md de silex).

### Fase H — LIVE escalonado

Binance Spot con capital mínimo → revisar semanal → añadir exchange solo con nueva spec y gates verdes. Cualquier salto de fase lo apruebas tú.

## 7. Cómo usamos las skills de silex

- anti-vibecode-sdd: flujo de 7 fases con aprobación humana, jerarquía de autoridad (petición → constitución → spec → AGENTS.md → guía) y marca \[NEEDS DECISION\] cuando falte una decisión.
- Verificación por valor: tests solo donde una regresión importa (dinero, riesgo, autenticación); parametrizar en vez de multiplicar tests. Ojo: crypto-bot hoy tiene la regla de un test por RF; se puede conciliar al abrir 011.
- Skills de UI (typeui-fundamentals, design-system): para pestañas nuevas del panel (Learning, Copy trading, Exchanges).
- Instalación en Claude Code: copiar .opencode/skills/\* a \~/.claude/skills/ (o .claude/skills/ del proyecto).
- docs/checklist.md: pasarlo antes de declarar terminada cada spec.

## 8. Herramientas para ahorrar tokens: graphify, ponytail y OmniRoute

Las tres funcionan en el agente donde se programa (Claude Code, OpenCode, Codex), no dentro de este chat de claude.ai: reducen lo que gasta cada sesión de trabajo, y la continuidad entre chats la da este documento.

| Herramienta | Qué hace | Lo que verifiqué | Cuidados | Veredicto |
| --- | --- | --- | --- | --- |
| [graphify](https://github.com/Graphify-Labs/graphify) | Convierte el repo en un grafo de conocimiento que se consulta en vez de leer archivos; el código se analiza localmente con tree-sitter, sin LLM | Lo ejecuté sobre crypto-bot: 2.910 nodos, 8.286 aristas, 154 comunidades, 0 tokens de LLM; probé `graphify explain` y `graphify path`. silex ya trae un plugin graphify.js que recuerda usar el grafo | graphify-out pesa \~8 MB (graph.json 4,5 MB, graph.html 3,5 MB): no versionarlo, como mucho GRAPH\_REPORT.md. Regenerar con `graphify update .` tras cambios | Usar ya |
| [ponytail](https://github.com/DietrichGebert/ponytail) | Plugin que inyecta reglas para escribir código mínimo y con test en la lógica de riesgo | Su README declara -45% de tokens y 98% de lógica riesgosa con test (68% sin él), en benchmarks propios con Opus 5.5; no los reproduje. Instala 3 hooks Node (SessionStart, SubagentStart, UserPromptSubmit); revisé su configuración, no audité el código de cada hook | Los hooks corren con tus permisos y este proyecto maneja claves de exchange: fijar versión y revisarlos antes de confiar. La constitución y la spec activa siguen mandando sobre sus reglas | Usar, tras revisar hooks |
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | Pasarela local (localhost:20128/v1) que enruta Claude Code y otros a muchos proveedores, con respaldo automático y compresión (RTK, Caveman) | Su README declara ahorros de 15–95% y \~1,62B tokens/mes en capas gratuitas; son cifras del autor, no verificadas | Todo prompt pasa por un proxy y puede salir a proveedores de terceros con modelos distintos de Claude y términos propios (el proyecto marca 13 como `tos: avoid`). La compresión con pérdida puede deformar código y cifras | Opcional, al final |

### Orden y reglas de uso

1. graphify primero: `uv tool install graphifyy`, luego `graphify install --platform claude` y, dentro del repo, `graphify update .`. Pedir al agente `graphify query` antes de abrir archivos sueltos.
2. ponytail en Claude Code con `/plugin marketplace add DietrichGebert/ponytail` y, en otro mensaje, `/plugin install ponytail@ponytail`.
3. OmniRoute solo si sigues chocando con límites, y con estas reglas: nunca claves de exchange ni .env en los prompts; compresión limitada a salidas de shell y tests (RTK) y apagada para specs y código de dinero o riesgo; sin proveedores marcados `avoid`.
4. Al abrir un chat nuevo se lee, en este orden: GRAPH\_REPORT.md, este plan y la spec activa. Nada más hasta que la tarea lo pida.

## 9. Expectativas honestas

- Con 20 USD y comisiones de 0,1% por lado, aunque la estrategia funcione, las ganancias absolutas serán mínimas. El éxito de esta etapa se mide en: sistema estable, métricas fiables y pérdidas acotadas.
- Pasivo total no existe todavía: hasta pasar las compuertas conviene revisar el informe diario.
- Si el backtest fuera de muestra no supera comisiones, la respuesta correcta es no operar con dinero real, no ajustar hasta que salga bonito.

## 10. Bloque de traspaso para pegar en un chat nuevo

```
Contexto: soy José. Proyecto: bot de trading cripto asistido por IA (inversión pasiva, procurar no perder dinero). Repo: https://github.com/JEJS-IA97/crypto-bot (master). Método y skills: https://github.com/JEJS-IA97/silex (SDD, una fase a la vez, aprobación humana entre fases).
Estado (2026-10-09): specs 001-009 completas; spec 010 Learning con T1-T2 hechas y T3-T7 pendientes (los tests rojos de learning son intencionales). Estrategia actual: ORB en Binance Spot, 20 USD, solo simulación/testnet. Constitución: docs/constitution.md (Binance Spot only en fase 1, dinero en Decimal, kill switch, tests como puerta, sin humo en IA). Plan completo: este documento (docs/plan-maestro).
Primero: clona el repo, ejecuta graphify update . y lee graphify-out/GRAPH_REPORT.md; usa graphify query antes de abrir archivos sueltos. Después lee docs/constitution.md, AGENTS.md y specs/010-learning/{spec,plan,tasks}.md. Implementa SOLO la tarea T3 (evaluate_hypothesis, RF-2) con tests primero, corre la suite completa, muestra el resultado, marca T3 y PÁRATE para mi aprobación.
Decisiones pendientes: D-1 a D-6 de la sección 5 del plan.
No implementes nada fuera de la spec activa; si falta una decisión, pregunta con [NEEDS DECISION].
```

## 11. Comandos y archivos clave

- Backend: cd backend; uvicorn app.main:app --reload
- Tests: cd backend; python -m unittest discover -s tests -p "test\_\*.py"
- Frontend: cd frontend; npm run dev · npm test · npm run lint
- Archivos: docs/constitution.md, AGENTS.md, specs/NNN-\*/, backend/app/services/bot\_loop.py, risk\_engine\_service.py, ai\_advisor\_service.py, learning\_service.py (en construcción), backend/app/domain/orb\_engine.py, render.yaml, claude\_master\_brief\_ai\_trading\_bot.md, docs/fase0-diagnostico-brief-ia.md
- Recomendación: guarda este documento en el repo como docs/plan-maestro.md para que el contexto viva en archivos, no en el chat.
