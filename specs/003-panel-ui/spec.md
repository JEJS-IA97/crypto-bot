# Spec 003 — Panel UI: rediseño con estándar anti-vibecode

Estado: borrador en revisión (pendiente aprobación del usuario).
Estándar de referencia: `ANTI_VIBECODE_GUIDE.md` (raíz, local, no versionado).

## Contexto

El panel (`frontend/src/pages/Simulation.jsx` + `index.css`) funciona: órdenes,
posiciones, métricas, kill switch, señal externa y token operan contra la API real.
Pero incumple el estándar visual/UX en revisión, y faltan dos piezas de producto.
La auditoría completa (con severidades) está en «Auditoría base» al final.

Quejas del usuario traducidas a requisitos:

1. «Sin simetría, un cuadro más grande que el otro» → RF-1.
2. «No hay paddings, botones feos» → RF-1, RF-2.
3. «Espacio en blanco como un marco» → RF-1.
4. «Me gustaría ver gráfica» → RF-3.
5. «Dice que opera pero no ve nada / no está la opción crypto copy» → RF-4, RF-5.

## Requisitos funcionales

- **RF-1 — Sistema de diseño y layout consistente.**
  - Tokens `:root` para color, espaciado, radio y tipografía; ningún hex/px
    arbitrario nuevo fuera de tokens.
  - Grids simétricos (columnas iguales salvo decisión explícita justificada en
    comentario), sin huecos huérfanos (hoy `.control-panels-grid` con 3 hijos
    en 2 columnas deja un hueco).
  - Escala de espaciado única aplicada a gutters, paddings de tarjeta y
    separación de secciones (hoy se mezclan 14/15/16/18/28 px).
  - Contenedor con `max-width` para que en pantallas grandes no se estire en
    «marco» (hoy `.simulation-page` solo tiene padding 42/44 px sin límite).
  - CSS organizado por secciones en orden lógico (hoy las reglas de
    metrics/kill-switch están después de los `@media`).

- **RF-2 — Jerarquía de botones.**
  - Escala de acciones: primaria, secundaria, destructiva (kill switch) y
    utilitaria; un solo tono verde de acción (hoy conviven `#00c878`,
    `#00b96e`, `#00bd72`).
  - Estados `:hover`, `:focus-visible`, `:disabled` visibles en todos los
    botones (hoy `:focus-visible` no existe en ningún botón/tab).

- **RF-3 — Gráfica de equity real.**
  - Curva de equity de la cuenta (dato real del backend, cero datos
    inventados) con estados loading / vacío / error diferenciados.
  - Sin dependencias nuevas: SVG nativo.
  - Se actualiza con la recarga normal del panel (junto a balance/trades).

- **RF-4 — Copy trading visible.**
  - La señal externa (RF-8 existente, sin RF nuevo) se presenta como
    «Copy trading» con etiqueta y texto que expliquen qué hace (envía una
    señal al bot que la evalúa en el próximo ciclo).

- **RF-5 — Formato y estados de datos.**
  - Eliminar notación exponencial en la UI (hoy «0E-8 USD» en métricas);
    formateo monetario centralizado y locale-aware (una sola `formatMoney`).

- **RF-6 — Layout de tres columnas según `design.json` (ronda 2).**
  - Fuente de verdad: `design.json` (raíz) + `ANTI_VIBECODE_STANDARD.json`.
    El usuario rechazó la ronda 1 («cajas y grids repetidas, igual que antes»).
  - Shell de tres columnas: **rail de navegación** (negro, iconos finos que
    cambian de pestaña de verdad) + **workspace** (`#1D1E21`: cabecera,
    fila de métricas con iconos tipo «rounded square», pestañas
    OPERAR/ESTADO/HISTORIAL con `role=tablist` reales, contenido en
    columnas 36/64 como el original) + **sidebar negra** (cuenta con
    acciones reales, control del bot, copy trading, token, precios vivos).
  - Paleta y tipografía de `design.json` (turquesa `#27E7CF` como acento
    primario, fondo `#1D1E21`, superficies por color sin bordes, divisores
    `#303236`, sin fondos exteriores claros).
  - Sin «cardify»: las métricas del resumen son texto + icono sobre el
    fondo (sin tarjeta individual); secciones separadas por divisores
    finos, no por cajas con borde.
  - Scroll único y consistente: un solo `scrollbar` global estilado;
    sin contenedores con scroll interno de estilo distinto.
  - Datos reales únicamente: los precios vivos usan `marketPrices` real;
    **sin sparklines** (no hay serie por activo → sería dato falso).
  - `AccountBalanceTable` se elimina (duplica exactamente la fila de
    métricas del resumen).

## No funcionales

- Responsive: conservar los breakpoints actuales (1300/1050/700) y validar
  small mobile / tablet / laptop / desktop.
- Accesibilidad: `:focus-visible` con contraste, iconos decorativos
  `aria-hidden` (hoy anuncian «▣»), contraste mínimo WCAG AA, etiquetas de
  formulario asociadas (ya existen, conservar).
- Sin dependencias nuevas de frontend (bundle no debe crecer >5 %).
- Tests vitest en todos los componentes tocados; lint y build en verde.
- Nada de datos falsos: la gráfica solo usa series reales del backend.

## Fuera de alcance

- Backend, RFs de trading, fases, informe diario, keepalive.
- Auto-copy automático (RF futuro, no está en esta spec).
- Router/multipágina, tema claro, rediseño de copy fuera del panel.

## Decisiones

- **D-1**: gráfica en SVG nativo, sin librerías (estándar §21/§9).
- **D-2**: la serie de equity se deriva en el frontend a partir de datos
  reales ya disponibles (balance inicial + PnL realizado por operación +
  balance total actual como último punto); la etiqueta de la gráfica lo dice
  explícitamente para no implicationar datos que no existen como serie.
- **D-3**: trabajo en rama `ui-redesign`; push/merge a `master` (y por tanto
  Pages/Render) solo tras aprobación explícita del usuario.
- **D-4**: los archivos `ANTI_VIBECODE_*` de la raíz no se versionan
  (`.gitignore` local, sin commitear).
- **D-5**: no se renombran endpoints, contratos de API ni campos de datos.
- **D-6** (ronda 2): `design.json` manda sobre RF-1 de la ronda 1; se
  retira el `max-width` de contenedor (el dashboard es full-bleed, tres
  columnas) y se reemplaza la paleta propia por la de `design.json`.
- **D-7** (ronda 2): CSS modular en `src/styles/*.css` con `index.css`
  como única entrada (evita un CSS gigante; los tests de CSS concatenan
  los mismos archivos que importa `index.css`).

## Auditoría base (severidad, evidencia)

| # | Sev. | Hallazgo | Evidencia |
|---|------|----------|-----------|
| 1 | HIGH | Hueco en `.control-panels-grid` (3 hijos, 2 columnas) | index.css:874-878; 3.er panel medio vacío |
| 2 | HIGH | Cálculos de layout arbitrarios, asimétricos | index.css:202 `1.08fr/0.92fr`; :92 `0.85fr/4.15fr` |
| 3 | HIGH | «0E-8 USD» en métricas (notación exponencial al usuario) | captura del usuario; formateo sin centralizar |
| 4 | HIGH | Sin `:focus-visible` en botones/tabs | index.css solo `:focus` en inputs (:349) |
| 5 | MED | Escala de espaciado inexistente (14/15/16/18/26/28 px mezclados) | index.css:222,591,261,95… |
| 6 | MED | Hex arbitrarios fuera de tokens (3 verdes distintos) | `#00c878`(:11) vs `#00b96e`(:304) vs `#00bd72`(:384) |
| 7 | MED | Sin `max-width`: se estira en pantallas grandes + padding 42/44 px = «marco» | index.css:21-27 |
| 8 | MED | CSS fuera de orden (métricas/kill-switch tras los `@media`) | index.css:791-920 |
| 9 | MED | Página gigante: 700 líneas mezclando carga de datos, 3 tablas y layout | Simulation.jsx |
| 10 | LOW | Iconos-glifo decorativos sin `aria-hidden` (▣ ▤) | Simulation.jsx:369,612 |
| 11 | LOW | `!important` en clases de color | index.css:654,658 |
| 12 | LOW | Fechas sin locale explícito (`toLocaleString()` sin args) | Simulation.jsx:640 |
| 13 | REC | Gradiente decorativo en cabecera de cuenta | index.css:98-103 |
| 14 | REC | `status-dot`/badges: hoy con texto real, conservar solo si comunican estado | index.css:65-86 |

## Criterios de aceptación

- Auditoría #1-#12 sin reincidencia (grep/inspección) y captura del panel
  nuevo aprobada por el usuario.
- `npm test -- --run`, `npm run lint`, `npm run build` en verde.
- Gráfica renderizada con datos reales en local (cuenta con trades) y en prod
  tras aprobación.
