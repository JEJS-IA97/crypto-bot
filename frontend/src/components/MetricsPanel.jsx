import { useCallback, useEffect, useState } from "react";

import {
    getBotMetrics,
    getBotStatus,
    getDecisions,
} from "../api/bot";
import { formatMoney } from "../utils/format";

const REFRESH_MS = 5000;

function deriveState(status) {
    if (!status.breaker_active) {
        if (status.running) {
            return { label: "Activo", tone: "active", reason: null };
        }
        return { label: "Detenido", tone: "stopped", reason: null };
    }
    return {
        label: "Bloqueado",
        tone: "blocked",
        reason: status.breaker_reason || "Circuit breaker activo.",
    };
}

function money(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    return `${formatMoney(value)} USD`;
}

function decisionResult(decision) {
    if (decision.status === "REJECTED") {
        return decision.rejection_reason || "rechazada";
    }
    if (decision.pnl_usd !== null && decision.pnl_usd !== undefined) {
        return money(decision.pnl_usd);
    }
    return decision.status;
}

function decisionList(data) {
    const items = data && Array.isArray(data.decisiones)
        ? data.decisiones
        : [];
    return items;
}

function MetricsPanel({ refreshMs = REFRESH_MS }) {
    const [status, setStatus] = useState(null);
    const [metrics, setMetrics] = useState(null);
    const [decisions, setDecisions] = useState([]);
    const [rejected, setRejected] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const [
                nextStatus,
                nextMetrics,
                nextHistory,
                nextRejected,
            ] = await Promise.all([
                getBotStatus(),
                getBotMetrics(),
                getDecisions({ limit: 20 }),
                getDecisions({ status: "REJECTED", limit: 20 }),
            ]);

            setStatus(nextStatus);
            setMetrics(nextMetrics);
            setDecisions(decisionList(nextHistory));
            setRejected(decisionList(nextRejected));
            setError("");
        } catch (requestError) {
            console.error("Error cargando el panel del bot:", requestError);
            setError("No se pudo cargar el estado del bot.");
        } finally {
            setLoading(false);
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

    if (loading) {
        return (
            <section className="metrics-panel panel-card">
                <div className="panel-heading">
                    <div>
                        <span className="eyebrow">BOT STATUS</span>
                        <h2>Estado y métricas</h2>
                    </div>
                </div>
                <div className="loading-state">Cargando estado...</div>
            </section>
        );
    }

    const state = status ? deriveState(status) : null;
    const blockReason = state?.reason || metrics?.block_reason || null;

    return (
        <section
            className="metrics-panel panel-card"
            data-testid="metrics-panel"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">BOT STATUS</span>
                    <h2>Estado y métricas</h2>
                </div>

                {state && (
                    <span
                        className={`panel-caption state-${state.tone}`}
                        data-testid="bot-state"
                    >
                        {state.label}
                    </span>
                )}
            </div>

            {error && <div className="form-message error">{error}</div>}

            <div className="metrics-meta">
                <span>
                    Fase:{" "}
                    <strong data-testid="bot-phase">
                        {status?.fase || "—"}
                    </strong>
                </span>

                {blockReason && (
                    <span
                        className="metrics-reason"
                        data-testid="block-reason"
                    >
                        Motivo de bloqueo: {blockReason}
                    </span>
                )}
            </div>

            <div className="summary-grid metrics-grid">
                <article className="summary-card summary-blue">
                    <span>Saldo</span>
                    <strong data-testid="metric-balance">
                        {metrics ? money(metrics.balance_usd) : "—"}
                    </strong>
                    <small>Caja + valor de mercado</small>
                </article>

                <article className="summary-card summary-purple">
                    <span>Posiciones abiertas</span>
                    <strong>
                        {metrics ? metrics.open_positions : "—"}
                    </strong>
                    <small>Sin posición más allá del límite</small>
                </article>

                <article className="summary-card summary-green">
                    <span>PnL realizado</span>
                    <strong>
                        {metrics ? money(metrics.realized_pnl_usd) : "—"}
                    </strong>
                    <small>Decisiones cerradas</small>
                </article>

                <article className="summary-card summary-orange">
                    <span>PnL no realizado</span>
                    <strong>
                        {metrics ? money(metrics.unrealized_pnl_usd) : "—"}
                    </strong>
                    <small>Se hace real al cerrar</small>
                </article>

                <article className="summary-card summary-cyan">
                    <span>Drawdown</span>
                    <strong>
                        {metrics ? `${metrics.drawdown_pct}%` : "—"}
                    </strong>
                    <small>Caída desde el pico</small>
                </article>

                <article className="summary-card summary-yellow">
                    <span>Aperturas del día</span>
                    <strong>
                        {metrics ? metrics.opens_today : "—"}
                    </strong>
                    <small>Límite 10 por día</small>
                </article>

                <article className="summary-card summary-red">
                    <span>Pérdida del día</span>
                    <strong>
                        {metrics ? money(metrics.daily_loss_usd) : "—"}
                    </strong>
                    <small>Corte al 5% del capital</small>
                </article>
            </div>

            <div className="metrics-section">
                <h3>Señales rechazadas</h3>

                {rejected.length === 0 ? (
                    <div className="empty-state">
                        No hay señales rechazadas.
                    </div>
                ) : (
                    <ul
                        className="rejected-list"
                        data-testid="rejected-signals"
                    >
                        {rejected.map((decision) => (
                            <li key={decision.id}>
                                <strong>{decision.symbol}</strong>
                                {" — "}
                                {decision.side}
                                {" — "}
                                <code>
                                    {decision.rejection_reason ||
                                        "rechazada"}
                                </code>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="metrics-section">
                <h3>Historial de decisiones</h3>

                {decisions.length === 0 ? (
                    <div className="empty-state">
                        Todavía no hay decisiones.
                    </div>
                ) : (
                    <div className="data-table-wrapper">
                        <table
                            className="data-table"
                            data-testid="decisions-table"
                        >
                            <thead>
                                <tr>
                                    <th>Par</th>
                                    <th>Lado</th>
                                    <th>Origen</th>
                                    <th>Estado</th>
                                    <th>Resultado</th>
                                    <th>Señal (snapshot)</th>
                                </tr>
                            </thead>

                            <tbody>
                                {decisions.map((decision) => (
                                    <tr key={decision.id}>
                                        <td>
                                            <strong>
                                                {decision.symbol}
                                            </strong>
                                        </td>
                                        <td>{decision.side}</td>
                                        <td>{decision.origin}</td>
                                        <td>{decision.status}</td>
                                        <td>
                                            {decisionResult(decision)}
                                        </td>
                                        <td>
                                            <details
                                                data-testid={`decision-${decision.id}`}
                                            >
                                                <summary>ver</summary>
                                                <pre>
                                                    {JSON.stringify(
                                                        decision.snapshot,
                                                        null,
                                                        2
                                                    )}
                                                </pre>
                                            </details>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </section>
    );
}

export default MetricsPanel;
