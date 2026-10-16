# CLAUDE.md — crypto-bot

@AGENTS.md

## Antes de cualquier tarea
1. Lee `docs/contexto-2026-10-16/README.md`: es el traspaso completo de la sesión de investigación del 16-oct-2026 (diagnóstico del bot, backtest de referencia, decisiones propuestas, plan de 9 pasos, dirección del frontend). Abre los archivos de `research/` solo cuando la tarea los necesite.
2. Luego `docs/constitution.md` y la spec activa. Jerarquía: petición de José > constitución > spec activa > AGENTS.md > contexto.
3. Si existe `graphify-out/GRAPH_REPORT.md`, úsalo (`graphify query`) antes de abrir archivos sueltos.

## Reglas de trabajo con José
- Idioma: responde en español. Código e identificadores en inglés.
- SDD: una fase a la vez; para entre fases y espera aprobación. Marca `[NEEDS DECISION]` cuando falte una decisión.
- Pide confirmación antes de: registrar tareas programadas o servicios de Windows, enmendar la constitución, borrar archivos, hacer push.
- Nunca actives `ALLOW_LIVE_TRADING` ni muestres el contenido de `.env`.
