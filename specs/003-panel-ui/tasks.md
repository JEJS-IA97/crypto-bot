# Tareas — Spec 003 (Panel UI)

Depende de: aprobación del usuario sobre esta spec.
Flujo: cada tarea en rama `ui-redesign` → verde → checkbox → reporte → PÁATE.

- [x] **T0** — Aprobación de la spec por el usuario.
  - Hecho cuando: usuario dice «su»/«si» sobre spec.md.

- [x] **T1** — Tokens y layout base (RF-1).
  - Hecho cuando: `index.css` con tokens completos (color/espaciado/radio/tipo),
    grids simétricos, hueco de `.control-panels-grid` resuelto, contenedor con
    `max-width`, CSS reordenado por secciones; sin hex nuevos fuera de tokens.
  - Tests: test de regresión CSS simple (clase de contenedor existe) + build.

- [x] **T2** — Jerarquía de botones y estados (RF-2).
  - Hecho cuando: clases de acción (primaria/secundaria/destructiva/utilitaria)
    con hover/focus-visible/disabled; un solo verde de acción; tabs usan el
    mismo sistema.
  - Tests: vitest — botón muestra foco visible (clase/estilo) y estados.

- [x] **T3** — Gráfica de equity (RF-3, D-1, D-2).
  - Hecho cuando: componente `EquityChart` en SVG con serie derivada de
    trades+balance reales, estados loading/vacío/error, etiqueta de fuente de
    datos, montado en el panel.
  - Tests: vitest — render con serie, estado vacío, estado error; sin
    dependencias nuevas (package.json intacto).

- [x] **T4** — Copy trading visible (RF-4).
  - Hecho cuando: sección etiquetada «Copy trading» explica RF-8 sin cambiar
    el endpoint ni el contrato.
  - Tests: vitest — etiqueta y texto explicativo presentes.

- [x] **T5** — Formato de datos (RF-5).
  - Hecho cuando: `formatMoney` única, locale-aware, sin exponenciales en
    métricas/balance/posiciones.
  - Tests: vitest — `0` se muestra como `0.00`, no `0E-8`; valores grandes.

- [x] **T6** — Responsive + accesibilidad (NFR).
  - Hecho cuando: `:focus-visible` global, iconos decorativos `aria-hidden`,
    validación en 5 tamaños de viewport, contraste AA.
  - Tests: revisión manual + vitest (aria-hidden en iconos de empty state).

- [x] **T7** — Calidad de código (NFR).
  - Hecho cuando: `Simulation.jsx` dividido (carga de datos / secciones) sin
    perder comportamiento; `npm run lint` sin errores nuevos (los 2
    preexistentes de set-state-in-effect quedan documentados).
  - Tests: suite frontend completa en verde.

- [x] **T8** — Verificación final.
  - Hecho cuando: `npm test -- --run` + `npm run lint` + `npm run build`
    verdes; auditoría #1-#12 revisada sin reincidencia.
  - Evidence: salida de comandos en el reporte.

- [x] **T9** — Preview local + aprobación (D-3).
  - Hecho cuando: usuario prueba con `npm run dev` y aprueba el diseño.

- [x] **T10** — Merge y deploy.
  - Hecho cuando: `ui-redesign` → `master` tras aprobación; Pages redesplegado
    y panel en prod verificado (CORS + gráfica).

## Ronda 2 (feedback del usuario: usar `design.json`)

El T9 falló: «no diseñaste nada nuevo, puros cuadros y grids, scrolls
inconsistentes». El usuario indicó `design.json` (raíz) como fuente de
verdad → RF-6, D-6, D-7.

- [x] **T11** — Shell de tres columnas + paleta design.json (RF-6).
  - Hecho cuando: `app-shell` (rail 92px / workspace `#1D1E21` / sidebar
    negra) full-bleed sin fondos claros; tokens de `design.json` en
    `src/styles/tokens.css`; body con fondo `#1D1E21`; scroll global
    único estilado.
  - Tests: CSS tests actualizados (loader por imports), body bg, sin
    `!important`, contraste con la nueva paleta.

- [x] **T12** — Componentes nuevos (RF-6).
  - Hecho cuando: `NavRail` (iconos finos, navegación real a pestañas),
    `SectionTabs` (tablist accesible con teclado), `SummaryRow`
    (4 métricas con icono + tarjeta central de cuenta), `Sidebar`
    (cuenta+acciones reales, control, copy, token, precios) y
    `LivePrices` (precios reales de `marketPrices`, sin sparklines);
    `AccountBalanceTable` eliminado.
  - Tests: Simulation test actualizado (cambio de pestañas + aria),
    test de pestañas con teclado.

- [x] **T13** — CSS modular + responsive (RF-6, D-7).
  - Hecho cuando: `index.css` importa `styles/{tokens,base,layout,components}.css`;
    paneles sin bordes (superficie por color + divisores finos); breakpoints
    1300/1050/700 (rail colapsa, sidebar bajo el workspace);
    `:focus-visible` y jerarquía de botones conservados (primaria turquesa,
    destructiva en contorno rojo, acciones blancas).
  - Tests: lint 0, build OK, media queries presentes.

- [x] **T14** — Verificación ronda 2.
  - Hecho cuando: suites frontend+backend verdes, lint/build OK, y captura
    del panel nuevo aprobada por el usuario (T9 reabierto).
