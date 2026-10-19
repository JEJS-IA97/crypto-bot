import { getTrend } from "../../api/bot";
import { coin, price } from "./fmt";
import usePoll from "./usePoll";

function NowPanel({ board }) {
    const { data, error } = usePoll(getTrend, 60000);
    const regimes = board?.feed?.regimes || {};
    const prices = board?.feed?.prices || {};
    return (
        <section className="panel">
            <h2>Qué hace el bot ahora</h2>
            {error && <p className="note">{error}</p>}
            <table className="grid compact">
                <thead>
                    <tr>
                        <th>Par</th>
                        <th className="r">Precio</th>
                        <th>Tendencia diaria</th>
                        <th>Régimen 1 h</th>
                    </tr>
                </thead>
                <tbody>
                    {(data?.pairs || []).map((p) => (
                        <tr key={p.symbol} title={p.action}>
                            <td><strong>{coin(p.symbol)}</strong></td>
                            <td className="r num">{price(prices[p.symbol] ?? p.close)}</td>
                            <td>
                                <span className={`chip ${p.signal === "DENTRO" ? "up" : p.signal === "FUERA" ? "down" : ""}`}>{p.signal}</span>{" "}
                                <span className="dim">{p.dist_fast_pct !== undefined ? `${Number(p.dist_fast_pct) > 0 ? "+" : ""}${Number(p.dist_fast_pct).toFixed(1)} % vs SMA50 · ` : ""}{p.action}</span>
                            </td>
                            <td className="dim">{regimes[p.symbol] || "—"}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
            {data?.next_decision_utc && (
                <p className="foot">Próxima decisión diaria: {new Date(`${data.next_decision_utc}Z`).toLocaleString("es-VE", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })}</p>
            )}
        </section>
    );
}

export default NowPanel;
