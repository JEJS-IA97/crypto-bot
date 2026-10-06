# Spec 004 — Informe diario en HTML con el diseño del panel

## Contexto

El informe diario (spec 002, RF-3/RF-5) llega por correo en texto plano sin
estructura visual. Feedback del usuario (ronda 2): «haz que tengan el mismo
diseño que el front». Fuente de verdad del diseño: `design.json` en la raíz
(misma paleta que el panel: fondo `#1d1e21`, tarjetas `#202124`, acento
turquesa `#27e7cf`, negativo `#ff4d5a`, positivo `#21d99b`, etiquetas
`#929292`, texto `#f2f2f2`, divisores `#303236`).

## Requisitos funcionales

- **RF-1** — El envío es `multipart/alternative`: texto plano (fallback,
  contrato inalterado) + HTML. Un cliente que no renderice HTML sigue
  recibiendo el informe completo de siempre.
- **RF-2** — El HTML se genera de la **misma fuente de datos** que el texto
  (una sola recolección, dos renderers): mismas secciones, mismos valores,
  «sin datos» cuando falta la fuente; el informe nunca falla por datos
  ausentes (RF-5 de spec 002).
- **RF-3** — El HTML usa la paleta/tipografía del panel con CSS **inline**
  (sin JS ni hojas externas), tarjetas redondeadas de 600 px, números con
  `tabular-nums`, y las secciones: cabecera + badge de fase, Estado, Balance,
  PnL, Día UTC, Últimas 24 h, Breaker y pie.
- **RF-4** — Todo valor dinámico (motivos, razones de bloqueo, etc.) se
  escapa con `html.escape`; ningún HTML procedente de la BD se inyecta.
- **RF-5** — Sin `REPORT_TO`, `SMTP_USER` o `SMTP_PASS` sigue fallando
  cerrado antes de abrir conexión; si el HTML no se pudiera construir, la
  capa de envío aún puede mandar solo texto (el `html` es opcional).

## Decisiones

- **D-1** — Fuente única: `_collect_report` devuelve `ReportData`
  (`dataclass(frozen=True)`); los renderers de texto y HTML la consumen.
  `build_daily_report` no cambia de contrato.
- **D-2** — `send_email` acepta `html: str | None` y usa
  `EmailMessage.add_alternative(..., subtype="html")`.
- **D-3** — El CLI `send_daily_report.py` construye ambas partes y las pasa
  juntas; el workflow `daily-report.yml` no cambia.

## Tareas

- [x] **T1** — Tests rojos: `build_daily_report_html` (paleta, sin datos,
  igualdad de datos, escaping), `send_email(html=...)` (multipart), CLI
  (pasa `html=`).
- [x] **T2** — `report_service`: `_collect_report` + `ReportSummary` +
  `build_daily_report_html` (texto sin cambios).
- [x] **T3** — `email_service`: parte HTML opcional.
- [x] **T4** — CLI `send_daily_report` + suite completa + ruff.
