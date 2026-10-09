import { useCallback, useEffect, useState } from "react";

import {
    getAiStats,
    getBotMetrics,
    getBotStatus,
    getDecisions,
} from "../api/bot";
import { getSources } from "../api/observability";
import { formatMoney } from "../utils/format";

const REFRESH_MS = 5000;

function deriveOperationalState(status) {
    if (!status) {
        return { label: "—", tone: "stopped", detail: null };
    }
    if (status.breaker_active) {
        return {
            label: "EMERGENCIA",
            tone: "blocked",
            detail: status.breaker_reason || "breaker activo",
        };
    }
    if (!status.running) {
        return { label: "PAUSADO", tone: "stopped", detail: null };
    }
    return { label: "OPERANDO", tone: "active", detail: null };
}

function money(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    return `${formatMoney(value)} USD`;
}

function sourcesSummary(sources) {
    if (!Array.isArray(sources) || sources.length === 0) {
        return "—";
    }
    const counts = {};
    for (const source of sources) {
        counts[source.state] = (counts[source.state] || 0) + 1;
    }
    return Object.entries(counts)
        .map(([state, count]) => `${state} ${count}`)
        .join(" · ");
}

function utcNow() {
    return new Date().toUTCString();
}

function HeaderPanel({ refreshMs = REFRESH_MS }) {
    const [status, setStatus] = useState(null);
    const [metrics, setMetrics] = useState(null);
    const [aiStats, setAiStats] = useState(null);
    const [aiAvailable, setAiAvailable] = useState(true);
    const [sources, setSources] = useState(null);
    const [closedCount, setClosedCount] = useState(null);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        const results = await Promise.allSettled([
            getBotStatus(),
            getBotMetrics(),
            getAiStats(),
            getSources(),
            getDecisions({ status: "CLOSED", limit: 100 }),
        ]);
        const [statusResult, metricsResult, aiResult, sourcesResult, closedResult] =
            results;

        if (
            statusResult.status === "rejected" &&
            metricsResult.status === "rejected"
        ) {
            console.error("Error cargando el header:", statusResult.reason);
            setError("No se pudo cargar el estado del bot.");
            return;
        }

        setStatus(
            statusResult.status === "fulfilled" ? statusResult.value : null
        );
        setMetrics(
            metricsResult.status === "fulfilled" ? metricsResult.value : null
        );
        setAiStats(
            aiResult.status === "fulfilled" ? aiResult.value : null
        );
        setAiAvailable(aiResult.status === "fulfilled");
        setSources(
            sourcesResult.status === "fulfilled" ? sourcesResult.value : null
        );
        const closed =
            closedResult.status === "fulfilled" ? closedResult.value : null;
        setClosedCount(
            closed && Array.isArray(closed.decisiones)
                ? closed.decisiones.length
                : null
        );
        setError("");
    }, []);

    useEffect(() => {
        // load() es async: ningún setState ocurre de forma síncrona
        // dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
        const timer = setInterval(load, refreshMs);
        return () => clearInterval(timer);
    }, [load, refreshMs]);

    const operational = deriveOperationalState(status);
    const pnlTotal =
        metrics !== null
            ? Number(metrics.realized_pnl_usd || 0) +
              Number(metrics.unrealized_pnl_usd || 0)
            : null;

    return (
        <section
            className="header-panel panel-card"
            data-testid="header-panel"
            aria-label="Cabecera de la consola"
        >
            <div className="metrics-meta">
                <span>
                    Estado:{" "}
                    <strong data-testid="header-state">
                        {operational.label}
                    </strong>
                </span>
                <span>
                    Fase:{" "}
                    <strong data-testid="header-phase">
                        {status?.fase || "—"}
                    </strong>
                </span>
                <span data-testid="header-clock">
                    {utcNow()} (UTC)
                </span>
                {operational.detail && (
                    <span
                        className="metrics-reason"
                        data-testid="header-detail"
                    >
                        {operational.detail}
                    </span>
                )}
            </div>

            {error && <div className="form-message error">{error}</div>}

            <div className="summary-grid metrics-grid">
                <article className="summary-card summary-blue">
                    <span>Capital</span>
                    <strong data-testid="header-capital">
                        {metrics ? money(metrics.balance_usd) : "—"}
                    </strong>
                </article>

                <article className="summary-card summary-green">
                    <span>PnL diario</span>
                    <strong data-testid="header-pnl-daily">
                        {metrics
                            ? money(metrics.daily_realized_pnl_usd)
                            : "—"}
                    </strong>
                </article>

                <article className="summary-card summary-green">
                    <span>PnL total</span>
                    <strong data-testid="header-pnl-total">
                        {pnlTotal === null
                            ? "—"
                            : money(String(pnlTotal))}
                    </strong>
                </article>

                <article className="summary-card summary-cyan">
                    <span>Drawdown</span>
                    <strong data-testid="header-drawdown">
                        {metrics ? `${metrics.drawdown_pct}%` : "—"}
                    </strong>
                </article>

                <article className="summary-card summary-purple">
                    <span>Operaciones abiertas</span>
                    <strong data-testid="header-open">
                        {metrics ? metrics.open_positions : "—"}
                    </strong>
                </article>

                <article className="summary-card summary-orange">
                    <span>Operaciones cerradas</span>
                    <strong data-testid="header-closed">
                        {closedCount === null
                            ? "—"
                            : closedCount >= 100
                              ? "100+"
                              : closedCount}
                    </strong>
                </article>
            </div>

            <div className="metrics-meta">
                <span>
                    Consultas IA (24 h):{" "}
                    <strong data-testid="header-ai-queries">
                        {aiAvailable && aiStats
                            ? aiStats.queries_24h
                            : "sin datos"}
                    </strong>
                </span>
                <span>
                    Coste IA (24 h):{" "}
                    <strong data-testid="header-ai-cost">
                        {aiAvailable && aiStats
                            ? `${aiStats.cost_usd_24h} USD`
                            : "sin datos"}
                    </strong>
                </span>
                <span>
                    Latencia media IA:{" "}
                    <strong data-testid="header-ai-latency">
                        {aiAvailable && aiStats
                            ? aiStats.avg_latency_ms !== null
                                ? `${aiStats.avg_latency_ms} ms`
                                : "—"
                            : "sin datos"}
                    </strong>
                </span>
                <span>
                    Salud de fuentes:{" "}
                    <strong data-testid="header-sources">
                        {sources ? sourcesSummary(sources.sources) : "—"}
                    </strong>
                </span>
            </div>

            <div className="metrics-meta">
                <span data-testid="header-updated">
                    Datos actualizados:{" "}
                    {metrics?.generated_at ||
                        aiStats?.generated_at ||
                        utcNow()}
                </span>
            </div>
        </section>
    );
}

export default HeaderPanel;
