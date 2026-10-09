import { useCallback, useEffect, useState } from "react";

import { getPipeline } from "../api/observability";

const REFRESH_MS = 5000;

const STATE_LABELS = {
    HEALTHY: "Saludable",
    DEGRADED: "Degradado",
    STALE: "Obsoleto",
    ERROR: "Error",
    DISABLED: "Desactivado",
};

const STATE_TONES = {
    HEALTHY: "active",
    DEGRADED: "stopped",
    STALE: "stopped",
    ERROR: "blocked",
    DISABLED: "stopped",
};

function NodeBadge({ node }) {
    const tone = STATE_TONES[node.state] || "stopped";
    return (
        <span className={`panel-caption state-${tone}`}>
            {STATE_LABELS[node.state] || node.state}
        </span>
    );
}

function PipelineCanvas({ onSelect, refreshMs = REFRESH_MS }) {
    const [nodes, setNodes] = useState([]);
    const [selected, setSelected] = useState(null);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const payload = await getPipeline();
            setNodes(Array.isArray(payload.nodes) ? payload.nodes : []);
            setError("");
        } catch (requestError) {
            console.error("Error cargando el pipeline:", requestError);
            setError("No se pudo cargar el estado del pipeline.");
        }
    }, []);

    useEffect(() => {
        // load() es async: ningún setState ocurre de forma síncrona
        // dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
        const timer = setInterval(load, refreshMs);
        return () => clearInterval(timer);
    }, [load, refreshMs]);

    const handleSelect = (node) => {
        setSelected(node);
        if (onSelect) {
            onSelect(node);
        }
    };

    return (
        <section
            className="pipeline-canvas panel-card"
            data-testid="pipeline-canvas"
            aria-label="Canvas del pipeline"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">PIPELINE</span>
                    <h2>Nodos del sistema</h2>
                </div>
            </div>

            {error && <div className="form-message error">{error}</div>}

            {nodes.length === 0 ? (
                <div className="empty-state">Sin nodos que mostrar.</div>
            ) : (
                <div className="pipeline-grid">
                    {nodes.map((node) => (
                        <button
                            key={node.id}
                            type="button"
                            className="pipeline-node"
                            data-testid={`node-${node.id}`}
                            onClick={() => handleSelect(node)}
                        >
                            <span className="node-label">{node.label}</span>
                            <NodeBadge node={node} />
                            {node.reason && (
                                <small className="node-reason">
                                    {node.reason}
                                </small>
                            )}
                        </button>
                    ))}
                </div>
            )}

            {selected && (
                <div
                    className="metrics-section"
                    data-testid="node-detail"
                >
                    <h3>{selected.label}</h3>
                    <pre>
                        {JSON.stringify(
                            {
                                backing: selected.backing,
                                last_update: selected.last_update,
                                reason: selected.reason,
                                last_event: selected.last_event,
                            },
                            null,
                            2
                        )}
                    </pre>
                </div>
            )}
        </section>
    );
}

export default PipelineCanvas;
