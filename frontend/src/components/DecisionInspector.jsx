import { useCallback, useEffect, useState } from "react";

import { getDecisions } from "../api/bot";
import WhyPanel from "./WhyPanel";
import ReplayView from "./ReplayView";
import Timeline from "./Timeline";

function DecisionInspector({ selectedDecisionId = null, onSelect }) {
    const [decisiones, setDecisiones] = useState([]);
    const [internalId, setInternalId] = useState(null);
    const selectedId = selectedDecisionId ?? internalId;

    const loadDecisions = useCallback(async () => {
        try {
            const payload = await getDecisions({ limit: 20 });
            setDecisiones(
                Array.isArray(payload.decisiones)
                    ? payload.decisiones
                    : []
            );
        } catch (requestError) {
            console.error(
                "Error cargando las decisiones:",
                requestError
            );
            setDecisiones([]);
        }
    }, []);

    useEffect(() => {
        // loadDecisions() es async: ningún setState ocurre de forma
        // síncrona dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        loadDecisions();
    }, [loadDecisions]);

    const handleChange = (event) => {
        const raw = event.target.value;
        const value = raw === "" ? null : Number(raw);
        setInternalId(value);
        if (onSelect) {
            onSelect(value);
        }
    };

    return (
        <section
            className="metrics-section panel-card"
            data-testid="decision-inspector"
            aria-label="Inspector de decisiones"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">INSPECTOR</span>
                    <h2>Why?, replay y timeline de una decisión</h2>
                </div>
            </div>

            <label htmlFor="decision-select">
                Decisión a inspeccionar
            </label>
            <select
                id="decision-select"
                value={selectedId ?? ""}
                onChange={handleChange}
            >
                <option value="">
                    Selecciona una decisión…
                </option>
                {decisiones.map((decision) => (
                    <option
                        key={decision.id}
                        value={decision.id}
                    >
                        #{decision.id} · {decision.symbol} ·{" "}
                        {decision.side}
                    </option>
                ))}
            </select>

            {selectedId === null ? (
                <div className="empty-state">
                    Selecciona una decisión para inspeccionarla.
                </div>
            ) : (
                <div className="history-stack">
                    <WhyPanel decisionId={selectedId} />
                    <ReplayView decisionId={selectedId} />
                    <Timeline decisionId={selectedId} />
                </div>
            )}
        </section>
    );
}

export default DecisionInspector;
