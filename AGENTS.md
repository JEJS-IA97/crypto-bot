# AGENTS.md — crypto-bot

## Proyecto
Bot de trading de cripto con capital mínimo (20 USD), **solo Binance Spot**, decidido por señales/estrategias evaluadas primero en paper-trading y backtest. Fases: simulación → testnet → real.

Stack: Python 3.14 + FastAPI + SQLAlchemy + Pydantic (backend en `backend/`), React 19 + Vite (frontend en `frontend/`).
Estructura: specs en `specs/`, docs en `docs/`, código en `backend/app/`, tests en `backend/tests/`.

## Comandos
- Ejecutar backend: `cd backend; .\.venv\Scripts\uvicorn.exe app.main:app --reload`
- Ejecutar frontend: `cd frontend; npm run dev`
- Tests: `cd backend; .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
- Lint/formato: `cd backend; .\.venv\Scripts\python.exe -m ruff check .` (pendiente de instalar ruff)

## Estilo y convenciones
- Dinero y cantidades en `Decimal`; prohibido `float` para valores monetarios.
- Código e identificadores en inglés; docs, mensajes de UI y specs en español.
- Tipado completo en funciones públicas; `dataclass(frozen=True)`/`Enum` para modelos de dominio; Pydantic v2 en la API.
- Cada servicio tiene su test en `backend/tests/`; los clientes de exchange se testean con `httpx` mockeado (sin red).

## Reglas
- Lee `docs/constitution.md` y la spec activa antes de tocar código.
- No implementes nada que no esté en la spec activa. Si falta una decisión, pregunta.
- Un requisito funcional (RF) sin test es un RF no implementado.
- No avances con tests en rojo.
- Ninguna orden con dinero real sin `ALLOW_LIVE_TRADING=true` (ver constitución, puntos 3-4).

## Al terminar cualquier tarea
- Ejecuta `cd backend; .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` y muestra el resultado completo.
- Marca el checkbox correspondiente en `specs/NNN-*/tasks.md`.
- Reporta: tarea, RF cubiertos, resultado de tests, siguiente tarea propuesta. PÁRATE y espera aprobación.
