import { useCallback, useEffect, useState } from "react";

import { getEvents } from "../api/observability";
import { groupByCorrelation, EVENT_LABELS } from "../utils/events";

const REFRESH_MS = 5000;
const DEFAULT_LIMIT = 50;

function payloadSummary(payload) {
    if (!payload || Object.keys(payload).length === 0) {
        return null;
    }
    return JSON.stringify(payload, null, 2);
}

function EventStream({
    correlationId = null,
    refreshMs = REFRESH_MS,
    limit = DEFAULT_LIMIT,
}) {
    const [events, setEvents] = useState([]);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const params = { limit };
            if (correlationId) {
                params.correlation_id = correlationId;
            }
            const payload = await getEvents(params);
            setEvents(Array.isArray(payload.events) ? payload.events : []);
            setError("");
        } catch (requestError) {
            console.error("Error cargando los eventos:", requestError);
            setError("No se pudo cargar el recorrido de eventos.");
        }
    }, [correlationId, limit]);

    useEffect(() => {
        // load() es async: ningún setState ocurre de forma síncrona
        // dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
        const timer = setInterval(load, refreshMs);
        return () => clearInterval(timer);
    }, [load, refreshMs]);

    const groups = groupByCorrelation(events);

    return (
        <section
            className="event-stream panel-card"
            data-testid="event-stream"
            aria-label="Recorrido de eventos"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">EVENTOS EN VIVO</span>
                    <h2>Recorrido por correlación</h2>
                </div>
            </div>

            {error && <div className="form-message error">{error}</div>}

            {groups.length === 0 ? (
                <div className="empty-state">Sin actividad registrada.</div>
            ) : (
                groups.map((group) => (
                    <div
                        key={group.correlationId || "sin-correlacion"}
                        className="metrics-section"
                        data-testid={`flow-${group.correlationId || "sin-correlacion"}`}
                    >
                        <h3>
                            Correlación:{" "}
                            {group.correlationId || "sin correlación"}
                        </h3>

                        <ol className="event-list">
                            {group.events.map((event) => {
                                const summary = payloadSummary(
                                    event.payload
                                );
                                return (
                                    <li
                                        key={event.id}
                                        data-testid={`event-${event.event}`}
                                    >
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
                                        {" · latencia "}
                                        {event.latency_ms !== null &&
                                        event.latency_ms !== undefined
                                            ? `${event.latency_ms} ms`
                                            : "—"}
                                        {" · "}
                                        {event.result}
                                        {" · corr "}
                                        {event.correlation_id || "—"}
                                        {summary && (
                                            <pre className="event-payload">
                                                {summary}
                                            </pre>
                                        )}
                                    </li>
                                );
                            })}
                        </ol>
                    </div>
                ))
            )}
        </section>
    );
}

export default EventStream;
