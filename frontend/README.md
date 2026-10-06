# crypto-bot — frontend

Panel de control del bot (React 19 + Vite). Comunicación con el backend FastAPI
(`backend/`, por defecto en `http://localhost:8000`).

## Comandos (desde `frontend/`)

| Acción | Comando |
| --- | --- |
| Dev server | `npm run dev` |
| Tests (vitest + Testing Library) | `npm test` |
| Lint | `npm run lint` |
| Build de producción | `npm run build` |

## Estructura

- `src/pages/` — `Simulation.jsx` (panel principal: estado, métricas, control y señales)
- `src/components/` — `MetricsPanel` (estado y métricas, RF-17/RF-18),
  `KillSwitch` (arrancar/detener, RF-3/RF-19), `ExternalSignalForm`
  (señal externa, RF-8/RF-19), `TradingPanel`, …
- `src/api/` — clientes HTTP (`bot.js`, `signals.js`, `simulation.js`, `client.js`)
- `src/test/setup.js` — arranque de vitest (jsdom + jest-dom)

Mensajes de UI y textos en español; los motivos de reacción en inglés vienen del backend.
