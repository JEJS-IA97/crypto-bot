import { useCallback, useEffect, useState } from "react";

import { getDecisionReplay } from "../api/bot";
import { EVENT_LABELS } from "../utils/events";

function ReplayView({ decisionId }) {
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
            const payload = await getDecisionReplay(decisionId);
            setData(payload);
            setError("");
        } catch (requestError) {
            console.error(
                "Error cargando el replay:",
                requestError
            );
            setData(null);
            setError("No se pudo cargar el replay de la decisión.");
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
            <div className="empty-state" data-testid="replay-loading">
                Cargando replay…
            </div>
        );
    }

    if (error) {
        return <div className="form-message error">{error}</div>;
    }

    if (!data) {
        return null;
    }

    const {
        decision,
        snapshot,
        events,
        ai_evaluation: aiEvaluation,
        position,
        outcome,
        unavailable,
    } = data;

    return (
        <section
            className="metrics-section panel-card"
            data-testid="replay-view"
            aria-label={`Replay de la decisión ${decisionId}`}
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">REPLAY</span>
                    <h2>
                        Reconstrucción de la decisión #{decision.id}
                    </h2>
                </div>
            </div>

            <div className="metrics-section" data-testid="replay-snapshot">
                <h3>Snapshot</h3>
                <p>
                    {decision.symbol} · {decision.side} · precio{" "}
                    {snapshot.price ?? "—"} · corr{" "}
                    {snapshot.correlation_id ?? "—"}
                </p>
                <pre className="event-payload">
                    {JSON.stringify(
                        {
                            indicators: snapshot.indicators,
                            candles: snapshot.candles,
                            config: snapshot.config,
                        },
                        null,
                        2
                    )}
                </pre>
            </div>

            <div className="metrics-section" data-testid="replay-events">
                <h3>Eventos registrados</h3>
                {events.length === 0 ? (
                    <div className="empty-state">
                        Sin eventos registrados.
                    </div>
                ) : (
                    <ol className="event-list">
                        {events.map((event) => (
                            <li key={event.id}>
                                <time dateTime={event.created_at}>
                                    {String(event.created_at)}
                                </time>
                                {" · "}
                                {event.service}
                                {" · "}
                                <strong>
                                    {EVENT_LABELS[event.event] ||
                                        event.event}
                                </strong>
                                {" · "}
                                {event.result}
                            </li>
                        ))}
                    </ol>
                )}
            </div>

            {aiEvaluation ? (
                <div className="metrics-section" data-testid="replay-ai">
                    <h3>Evaluación IA</h3>
                    <p>
                        {aiEvaluation.decision} ·{" "}
                        {aiEvaluation.model} · coste{" "}
                        {aiEvaluation.cost_usd} USD
                    </p>
                </div>
            ) : null}

            {position ? (
                <div
                    className="metrics-section"
                    data-testid="replay-position"
                >
                    <h3>Posición</h3>
                    <p>
                        {position.symbol} · {position.quantity} @{" "}
                        {position.average_entry_price} ·{" "}
                        {position.status}
                    </p>
                </div>
            ) : null}

            <div
                className="metrics-section"
                data-testid="replay-outcome"
            >
                <h3>Resultado</h3>
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
            </div>

            {unavailable.length > 0 && (
                <div data-testid="replay-unavailable">
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

export default ReplayView;
