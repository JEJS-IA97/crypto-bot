import { useCallback, useEffect, useState } from "react";

import { getBotStatus, startBot, stopBot } from "../api/bot";

const REFRESH_MS = 5000;

function deriveState(status) {
    if (status.breaker_active) {
        return {
            label: "Bloqueado",
            tone: "blocked",
            reason: status.breaker_reason || "Circuit breaker activo.",
        };
    }
    if (status.running) {
        return { label: "Activo", tone: "active", reason: null };
    }
    return { label: "Detenido", tone: "stopped", reason: null };
}

function KillSwitch({ refreshMs = REFRESH_MS }) {
    const [status, setStatus] = useState(null);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            setStatus(await getBotStatus());
        } catch (requestError) {
            console.error("Error leyendo el estado del bot:", requestError);
            setError("No se pudo leer el estado del bot.");
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

    const handleToggle = async () => {
        if (!status || busy) {
            return;
        }

        setBusy(true);
        setError("");
        setMessage("");

        try {
            const result = status.running
                ? await stopBot()
                : await startBot();

            setStatus((current) => ({
                ...current,
                running: result.running,
            }));
            setMessage(result.mensaje || "");
        } catch (requestError) {
            console.error("Error cambiando el estado:", requestError);
            setError(
                requestError.response?.data?.detail ||
                    "No se pudo cambiar el estado del bot."
            );
        } finally {
            setBusy(false);
        }
    };

    const state = status ? deriveState(status) : null;

    return (
        <section
            className="kill-switch panel-card"
            data-testid="kill-switch"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">KILL SWITCH</span>
                    <h2>Control del bot</h2>
                </div>

                {state && (
                    <span
                        className={`panel-caption state-${state.tone}`}
                        data-testid="kill-state"
                    >
                        {state.label}
                    </span>
                )}
            </div>

            {error && <div className="form-message error">{error}</div>}

            {message && (
                <div className="form-message success">{message}</div>
            )}

            {state?.reason && (
                <div
                    className="metrics-reason kill-reason"
                    data-testid="kill-reason"
                >
                    Motivo de bloqueo: {state.reason}
                </div>
            )}

            <p className="kill-note">
                {state?.label === "Activo"
                    ? "El bot está evaluando señales y puede abrir posiciones."
                    : "El bot no emitirá órdenes nuevas hasta que se arranque."}
            </p>

            <button
                type="button"
                className={`btn ${
                    status?.running ? "btn-danger" : "btn-primary"
                } btn-block`}
                onClick={handleToggle}
                disabled={!status || busy}
            >
                {!status
                    ? "Cargando..."
                    : status.running
                      ? "Detener"
                      : "Arrancar"}
            </button>
        </section>
    );
}

export default KillSwitch;
