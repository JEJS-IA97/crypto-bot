import { useCallback, useEffect, useState } from "react";

import { getTrend } from "../api/bot";

const REFRESH_MS = 60000;

const usd = new Intl.NumberFormat("es-VE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function formatPct(value) {
    if (value === undefined) {
        return "—";
    }
    const number = Number(value);
    return `${number > 0 ? "+" : ""}${number.toFixed(2)} %`;
}

function formatUtc(iso) {
    return new Date(`${iso}Z`).toLocaleString("es-VE", {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function TrendCard({ refreshMs = REFRESH_MS }) {
    const [trend, setTrend] = useState(null);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            setTrend(await getTrend());
            setError("");
        } catch (requestError) {
            console.error("Error leyendo la tendencia:", requestError);
            setError("No se pudo leer la señal de tendencia.");
        }
    }, []);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
        const timer = setInterval(load, refreshMs);
        return () => clearInterval(timer);
    }, [load, refreshMs]);

    return (
        <section className="data-section trend-card" aria-labelledby="trend-title">
            <div className="section-header">
                <div>
                    <span className="eyebrow">QUÉ HARÁ EL BOT HOY</span>
                    <h2 id="trend-title">Tendencia diaria (SMA50 y SMA200)</h2>
                </div>
                {trend && (
                    <p className="trend-next">
                        {trend.enabled ? "Próxima decisión" : "Núcleo desactivado"}
                        {trend.enabled && (
                            <strong> {formatUtc(trend.next_decision_utc)}</strong>
                        )}
                    </p>
                )}
            </div>

            {error && <p className="form-message error">{error}</p>}

            {trend && (
                <table className="trend-table">
                    <thead>
                        <tr>
                            <th scope="col">Par</th>
                            <th scope="col">Señal</th>
                            <th scope="col">Cierre</th>
                            <th scope="col">vs SMA50</th>
                            <th scope="col">vs SMA200</th>
                            <th scope="col">Acción</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trend.pairs.map((pair) => (
                            <tr key={pair.symbol}>
                                <th scope="row">{pair.symbol.replace("USDT", "")}</th>
                                <td>
                                    <span
                                        className={`trend-signal trend-signal--${
                                            pair.signal === "DENTRO" ? "in" : "out"
                                        }`}
                                    >
                                        {pair.signal}
                                    </span>
                                </td>
                                <td className="num">
                                    {pair.close ? usd.format(Number(pair.close)) : "—"}
                                </td>
                                <td className="num">{formatPct(pair.dist_fast_pct)}</td>
                                <td className="num">{formatPct(pair.dist_slow_pct)}</td>
                                <td>{pair.action}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </section>
    );
}

export default TrendCard;
