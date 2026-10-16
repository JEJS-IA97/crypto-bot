import { useCallback, useEffect, useState } from "react";

import { getLabBacktest, getLabLive, getLabTrades } from "../api/lab";

const REFRESH_MS = 10000;

const num = (value, digits = 2) =>
    value === null || value === undefined ? "—" : Number(value).toFixed(digits);

const signed = (value, digits = 2) => {
    if (value === null || value === undefined) {
        return "—";
    }
    const n = Number(value);
    return `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
};

const tone = (value) =>
    value > 0 ? "lab-pos" : value < 0 ? "lab-neg" : undefined;

function FeedStatus({ feed }) {
    if (!feed) {
        return null;
    }
    if (!feed.connected) {
        return (
            <p className="lab-feed lab-feed--down">
                Feed en vivo desconectado
                {feed.enabled === false ? " (laboratorio desactivado)" : ", reconectando…"}
            </p>
        );
    }
    return (
        <div className="lab-feed">
            <span className="status-dot" aria-hidden="true" />
            <span>
                En vivo · último precio hace {feed.seconds_since_tick ?? "—"} s
            </span>
            <ul className="lab-regimes">
                {feed.symbols.map((symbol) => (
                    <li key={symbol}>
                        <strong>{symbol.replace("USDT", "")}</strong>{" "}
                        {num(feed.prices?.[symbol])}{" "}
                        <span className="lab-muted">{feed.regimes?.[symbol]}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function Leaderboard({ rows, live }) {
    const sorted = [...rows].sort(
        (a, b) => b.return_pct - a.return_pct || a.capital - b.capital
    );
    return (
        <div className="lab-table-wrap">
            <table className="lab-table">
                <thead>
                    <tr>
                        <th scope="col">Estrategia</th>
                        <th scope="col" className="num">Capital</th>
                        <th scope="col" className="num">Trades</th>
                        <th scope="col" className="num">Long/Short</th>
                        <th scope="col" className="num">Acierto %</th>
                        <th scope="col" className="num">PF</th>
                        <th scope="col" className="num">Esperanza R</th>
                        <th scope="col" className="num">Retorno %</th>
                        <th scope="col" className="num">DD máx %</th>
                        {live && <th scope="col" className="num">Abiertas</th>}
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((row) => (
                        <tr key={`${row.strategy}-${row.capital}`}>
                            <th scope="row">{row.label}</th>
                            <td className="num">{num(row.capital, 0)}</td>
                            <td className="num">{row.trades}</td>
                            <td className="num">
                                {row.long_trades}/{row.short_trades}
                            </td>
                            <td className="num">{num(row.win_rate, 1)}</td>
                            <td className="num">{num(row.profit_factor)}</td>
                            <td className={`num ${tone(row.expectancy_r) ?? ""}`}>
                                {signed(row.expectancy_r)}
                            </td>
                            <td className={`num ${tone(row.return_pct) ?? ""}`}>
                                {signed(row.return_pct)}
                            </td>
                            <td className="num">{num(row.max_dd_pct, 1)}</td>
                            {live && <td className="num">{row.open_positions}</td>}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function LabTab({ refreshMs = REFRESH_MS }) {
    const [view, setView] = useState("live");
    const [liveData, setLiveData] = useState(null);
    const [backtest, setBacktest] = useState(null);
    const [trades, setTrades] = useState([]);
    const [error, setError] = useState("");

    const load = useCallback(async () => {
        try {
            const [liveBoard, recent] = await Promise.all([getLabLive(), getLabTrades(30)]);
            setLiveData(liveBoard);
            setTrades(recent);
            setError("");
        } catch (requestError) {
            console.error("Error leyendo el laboratorio:", requestError);
            setError("No se pudo leer el laboratorio.");
        }
    }, []);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        load();
        getLabBacktest().then(setBacktest).catch(() => setBacktest(null));
        const timer = setInterval(load, refreshMs);
        return () => clearInterval(timer);
    }, [load, refreshMs]);

    const rows = view === "live" ? liveData?.rows ?? [] : backtest?.rows ?? [];

    return (
        <section className="data-section lab" aria-labelledby="lab-title">
            <div className="section-header">
                <div>
                    <span className="eyebrow">TORNEO DE ESTRATEGIAS · PAPER</span>
                    <h2 id="lab-title">Laboratorio</h2>
                </div>
                <div className="lab-toggle" role="group" aria-label="Fuente del ranking">
                    <button
                        type="button"
                        aria-pressed={view === "live"}
                        onClick={() => setView("live")}
                    >
                        En vivo
                    </button>
                    <button
                        type="button"
                        aria-pressed={view === "backtest"}
                        onClick={() => setView("backtest")}
                    >
                        Backtest 365 días
                    </button>
                </div>
            </div>

            {error && <p className="form-message error">{error}</p>}
            <FeedStatus feed={liveData?.feed} />

            {view === "backtest" && backtest && (
                <p className="lab-muted">
                    {backtest.from} → {backtest.to} · {backtest.symbols.join(", ")} ·{" "}
                    {backtest.rules}
                </p>
            )}

            {rows.length ? (
                <Leaderboard rows={rows} live={view === "live"} />
            ) : (
                <p className="lab-muted">
                    {view === "live"
                        ? "Aún no hay operaciones cerradas en vivo."
                        : "Sin backtest todavía."}
                </p>
            )}

            <h3 className="lab-subtitle">Últimas operaciones en vivo</h3>
            {trades.length ? (
                <ul className="lab-trades">
                    {trades.map((t) => (
                        <li key={t.id}>
                            <span className={t.side === "LONG" ? "lab-pos" : "lab-neg"}>
                                {t.side === "LONG" ? "LONG" : "SHORT"}
                            </span>{" "}
                            {t.symbol.replace("USDT", "")} · {t.strategy} · {num(t.capital, 0)} USD ·{" "}
                            {t.status === "OPEN"
                                ? `abierta a ${num(t.entry)} (stop ${num(t.stop)}, objetivo ${num(t.take_profit)})`
                                : `cerrada por ${t.reason}: `}
                            {t.status !== "OPEN" && (
                                <strong className={tone(t.pnl)}>{signed(t.pnl, 4)} USD</strong>
                            )}
                            <span className="lab-muted"> · {t.regime}</span>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="lab-muted">Esperando la primera señal.</p>
            )}
        </section>
    );
}

export default LabTab;
