# Plan — Spec 010 (Learning)

Contratos y piezas previstos. La spec manda; si un contrato choca con la implementación, se cambia el plan, no la spec sin aprobación.

## Backend (nuevo, sin tocar 001-009)

### Modelos (`app/models.py`)

```python
class HypothesisStatus(str, Enum):
    PROPOSED, TESTING, VALIDATED, ACTIVE, DEPRECATED, REJECTED

class Hypothesis(Base):  # hypotheses
    id, statement (Text), origin_data_json (Text), case_count (int, 0),
    favorable_cases (int, 0), unfavorable_cases (int, 0),
    confidence (Numeric(8,6), nullable), observed_period_start/finish
    (DateTime, nullable), assets_json (Text), market_regime (String, nullable),
    status (SqlEnum), version (int, 1), source (String: operator|ai),
    evaluation_note (Text, nullable), rejection_reason (Text, nullable),
    created_at, updated_at

class Knowledge(Base):  # knowledge
    id, hypothesis_id (FK nullable), statement, evidence_json,
    sample_size (int), confidence_interval_json (Text nullable),
    works_when_json, fails_when_json, validated_at, version (int, 1),
    observed_impact (Text nullable), status (ACTIVE|DEPRECATED),
    rollback_reason (nullable), deprecated_at (nullable), created_at

class StrategyVersion(Base):  # strategy_versions (append-only)
    id, version (int), config_json, evidence_json, backtest_ref,
    paper_results_ref (nullable), motive, rolled_back_at (nullable),
    rollback_reason (nullable), created_at
```

`create_all` en `main.py` crea las tablas nuevas (sin alembic).

### Servicios (`app/services/learning_service.py`)

- `ALLOWED_TRANSITIONS`: dict de la máquina D-3 (+ `REJECTED` desde PROPOSED/TESTING).
- `create_hypothesis(db, data) -> Hypothesis` (status PROPOSED, version 1).
- `list_hypotheses(db, status=None, limit=50)`.
- `transition_hypothesis(db, h, to, reason=None)`: valida; `to=ACTIVE` exige motivo y crea `Knowledge`; `to=REJECTED` exige motivo; version += 1; emite eventos 008 (`service="learning"`).
- `evaluate_hypothesis(db, h, now)`: RF-2 (Decimal, Wald con z=1.96, umbrales de config); solo TESTING; devuelve h actualizada + `evaluation_note`.
- `list_knowledge(db, status=None)`.
- `register_strategy_version(db, data)` / `mark_rollback(db, version_row, reason)`.

### Config (`app/config.py`)

`learning_min_cases: int = 30`, `learning_min_favorable_ratio: str = "0.60"` (Decimal al cargar), `learning_window_days: int = 90`.

### API (`app/api/routes/learning.py`, prefijo `/api/learning`, tag `Learning`)

`GET /hypotheses`, `POST /hypotheses`, `POST /hypotheses/{id}/transition`,
`POST /hypotheses/{id}/evaluate`, `GET /knowledge`,
`GET /strategy-versions`, `POST /strategy-versions`, `POST /strategy-versions/{id}/rollback`.
Todas con `require_control_token` (patrón 001). Registrado en `main.py`.

### Eventos 005

`emit(service="learning", event=..., db=db)` en cada acción (RF-8).

### Cruce de evaluación (RF-2)

Consulta `SignalDecision` con `status=CLOSED`, `closed_at` dentro de la ventana, `symbol ∈ assets_json` (si declarado), `pnl_usd IS NOT NULL`. Favs: `pnl_usd > 0`; desfavs: `pnl_usd <= 0`. Sin universo declarado ⇒ nota "sin universo declarado" y sin evaluar.

## Frontend

- `src/api/learning.js`: `getHypotheses`, `createHypothesis`, `transitionHypothesis`, `evaluateHypothesis`, `getKnowledge`, `getStrategyVersions`.
- `src/components/LearningTab.jsx`: pestaña con dos columnas (grid), polling 5 s; estados vacíos; acciones (evaluar/transición) con confirmación.
- `src/components/HypothesisCard.jsx` (acento `--orange`): statement, source, casos fav/desfav/confianza, estado, fecha, faltantes = `max(0, umbral − case_count)`; nota de evaluación si existe.
- `src/components/KnowledgeCard.jsx` (acento `--positive`): statement, evidencia, intervalo, fechas, casos, efecto, rollback.
- Integración: `tabs.js` += `{id:"learning",label:"Learning"}`; `Simulation.jsx` monta `<LearningTab/>`.
- CSS con tokens existentes (sin hex nuevos); `designSystem.test.js`/`actionSystem.test.js` extendidos.

## Orden de tareas (TDD rojo→verde)

- T1 · Tests rojos backend (modelos + máquina de estados + API).
- T2 · Modelo + config + `learning_service` (crear/listar/transicionar) verdes.
- T3 · `evaluate_hypothesis` (RF-2) verdes.
- T4 · Knowledge + strategy_versions + eventos + API completa verdes; suite completa.
- T5 · Tests rojos frontend (LearningTab/HypothesisCard/KnowledgeCard + api).
- T6 · Frontend verde + integración pestaña + tests de diseño extendidos.
- T7 · Sin humo, docs (READMEs, estado `implementada`), RF-9 estática, validación final completa.

Al final de cada tarea: suite completa backend (+ ruff) y, si toca frontend, `npm run lint` + `npm test`; reporte con RF cubiertos y **PÁRATE**.
