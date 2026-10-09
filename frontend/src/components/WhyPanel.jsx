import { useCallback, useEffect, useState } from "react";

import { getDecisionWhy } from "../api/bot";

function renderValue(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    return String(value);
}

function Section({ title, testId, children }) {
    return (
        <div className="metrics-section" data-testid={testId}>
            <h3>{title}</h3>
            {children}
        </div>
    );
}

function WhyPanel({ decisionId }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        if (decisionId === null || decisionId === undefined) {
            setData(null);
            setError("");
            return;
        }
        setLoading(true);
        try {
            const payload = await getDecisionWhy(decisionId);
            setData(payload);
            setError("");
        } catch (requestError) {
            console.error("Error cargando el Why?:", requestError);
            setData(null);
            setError("No se pudo cargar el Why? de la decisión.");
        } finally {
            setLoading(false);
        }
    }, [decisionId]);

    useEffect(() => {
        // load() es async: ningún setState ocurre de forma síncrona
        // dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
    }, [load]);

    if (loading) {
        return (
            <div className="empty-state" data-testid="why-loading">
                Cargando Why?…
            </div>
        );
    }

    if (error) {
        return <div className="form-message error">{error}</div>;
    }

    if (!data) {
        return null;
    }

    const { decision, factors, ai, risk, outcome, unavailable } = data;

    return (
        <section
            className="metrics-section panel-card"
            data-testid="why-panel"
            aria-label={`Why? de la decisión ${decisionId}`}
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">WHY?</span>
                    <h2>
                        ¿Por qué la decisión #{decision.id} en{" "}
                        {decision.symbol}?
                    </h2>
                </div>
            </div>

            <p>
                {decision.side === "BUY" ? "Compra" : "Venta"} ·{" "}
                {decision.status}
                {decision.pnl_usd !== null &&
                    decision.pnl_usd !== undefined && (
                        <>
                            {" · PnL "}
                            {decision.pnl_usd} USD
                        </>
                    )}
            </p>

            <Section title="Factores a favor" testId="why-positive">
                {factors.positive.length === 0 ? (
                    <div className="empty-state">
                        Sin factores a favor registrados.
                    </div>
                ) : (
                    <ul className="event-list">
                        {factors.positive.map((factor) => (
                            <li key={factor}>{factor}</li>
                        ))}
                    </ul>
                )}
            </Section>

            <Section
                title="Factores en contra"
                testId="why-negative"
            >
                {factors.negative.length === 0 ? (
                    <div className="empty-state">
                        Sin factores en contra registrados.
                    </div>
                ) : (
                    <ul className="event-list">
                        {factors.negative.map((factor) => (
                            <li key={factor}>{factor}</li>
                        ))}
                    </ul>
                )}
            </Section>

            <Section
                title="Indicadores del snapshot"
                testId="why-indicators"
            >
                {Object.keys(factors.indicators).length === 0 ? (
                    <div className="empty-state">
                        Sin indicadores en el snapshot.
                    </div>
                ) : (
                    <pre className="event-payload">
                        {JSON.stringify(factors.indicators, null, 2)}
                    </pre>
                )}
            </Section>

            {ai ? (
                <Section title="Evaluación IA" testId="why-ai">
                    <p>
                        {ai.decision} · confianza{" "}
                        {renderValue(ai.confidence)} ·{" "}
                        {renderValue(ai.model)} · coste{" "}
                        {renderValue(ai.cost_usd)} USD ·{" "}
                        {renderValue(ai.latency_ms)} ms
                    </p>
                    {ai.risk_flags.length > 0 && (
                        <p>
                            Banderas:{" "}
                            {ai.risk_flags.join(", ")}
                        </p>
                    )}
                </Section>
            ) : null}

            {risk ? (
                <Section title="Evaluación de riesgo" testId="why-risk">
                    <p>
                        {renderValue(risk.action)} · abierto{" "}
                        {renderValue(risk.open_positions)} ·{" "}
                        comprometido {renderValue(risk.committed_usd)}{" "}
                        USD
                    </p>
                    {risk.reason && <p>Motivo: {risk.reason}</p>}
                </Section>
            ) : null}

            <Section title="Resultado" testId="why-outcome">
                <p>
                    {outcome.status}
                    {outcome.pnl_usd !== null &&
                        outcome.pnl_usd !== undefined && (
                            <>
                                {" · PnL "}
                                {outcome.pnl_usd} USD
                            </>
                        )}
                </p>
            </Section>

            {unavailable.length > 0 && (
                <div data-testid="why-unavailable">
                    <h3>Secciones no disponibles</h3>
                    <ul className="event-list">
                        {unavailable.map((item) => (
                            <li key={item.section}>
                                {item.section}: {item.reason}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </section>
    );
}

export default WhyPanel;
