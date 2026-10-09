import { useCallback, useEffect, useState } from "react";

import { getDecisionReplay } from "../api/bot";
import { EVENT_LABELS } from "../utils/events";

function Timeline({ decisionId }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        if (decisionId === null || decisionId === undefined) {
            setData(null);
            setError("");
            return;
        }
        try {
            const payload = await getDecisionReplay(decisionId);
            setData(payload);
            setError("");
        } catch (requestError) {
            console.error(
                "Error cargando la línea de tiempo:",
                requestError
            );
            setData(null);
            setError(
                "No se pudo cargar la línea de tiempo de la decisión."
            );
        }
    }, [decisionId]);

    useEffect(() => {
        // load() es async: ningún setState ocurre de forma síncrona
        // dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
    }, [load]);

    if (error) {
        return <div className="form-message error">{error}</div>;
    }

    if (!data) {
        return null;
    }

    const { decision, events, outcome, position, unavailable } = data;

    const items = [
        {
            key: "decision",
            stamp: decision.created_at,
            label: "Decisión creada",
            detail: `${decision.symbol} · ${decision.side}`,
        },
        ...events.map((event) => ({
            key: `event-${event.id}`,
            stamp: event.created_at,
            label: EVENT_LABELS[event.event] || event.event,
            detail: `${event.service} · ${event.result}`,
        })),
    ];

    if (position && position.closed_at) {
        items.push({
            key: "closed",
            stamp: position.closed_at,
            label: "Posición cerrada",
            detail:
                outcome.pnl_usd !== null &&
                outcome.pnl_usd !== undefined
                    ? `PnL ${outcome.pnl_usd}`
                    : "PnL —",
        });
    }

    const eventUnavailable = unavailable.find(
        (item) => item.section === "events"
    );

    return (
        <section
            className="metrics-section panel-card"
            aria-label={`Línea de tiempo de la decisión ${decisionId}`}
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">TIMELINE</span>
                    <h2>Línea de tiempo de la decisión</h2>
                </div>
            </div>

            <ol
                className="event-list"
                data-testid={`decision-timeline-${decisionId}`}
            >
                {items.map((item) => (
                    <li key={item.key}>
                        {item.stamp && (
                            <time dateTime={item.stamp}>
                                {String(item.stamp)}
                            </time>
                        )}
                        {" · "}
                        <strong>{item.label}</strong>
                        {" · "}
                        {item.detail}
                    </li>
                ))}
                {eventUnavailable && (
                    <li>
                        Recorrido de eventos no disponible:{" "}
                        {eventUnavailable.reason}.
                    </li>
                )}
            </ol>
        </section>
    );
}

export default Timeline;
