import { getLabTrades, getTelegram } from "../../api/lab";
import { clock, coin, price, signed, tone } from "./fmt";
import usePoll from "./usePoll";

export function TradeFeed() {
    const { data, error } = usePoll(() => getLabTrades(14), 15000);
    return (
        <section className="panel">
            <h2>Últimas operaciones del torneo</h2>
            {error && <p className="note">{error}</p>}
            <table className="grid compact">
                <tbody>
                    {(data || []).map((t) => (
                        <tr key={t.id}>
                            <td className="num dim">{clock(t.closed_ts || t.opened_ts)}</td>
                            <td>
                                <span className={t.side === "LONG" ? "up" : "down"}>{t.side === "LONG" ? "Compra" : "Venta"}</span> {coin(t.symbol)}
                                <div className="dim small">{t.strategy} · {t.capital}</div>
                            </td>
                            <td className="r num">
                                {t.status === "OPEN" ? (
                                    <span className="dim">abierta a {price(t.entry)}</span>
                                ) : (
                                    <span className={tone(t.pnl)}>{signed(t.pnl)}</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </section>
    );
}

export function TelegramFeed() {
    const { data, error } = usePoll(getTelegram, 20000);
    return (
        <section className="panel">
            <h2>Señales de Telegram</h2>
            {error && <p className="note">{error}</p>}
            {data && !data.configured && (
                <ol className="setup">
                    <li>Crea tu API en <a href="https://my.telegram.org" target="_blank" rel="noreferrer">my.telegram.org</a> (API development tools).</li>
                    <li>Pon <code>TELEGRAM_API_ID</code> y <code>TELEGRAM_API_HASH</code> en <code>backend/.env</code>.</li>
                    <li>Ejecuta <code>python telegram_login.py</code>: te pide el código que llega a tu Telegram y lista tus grupos.</li>
                    <li>Copia los ids de los grupos de señales a <code>TELEGRAM_CHATS</code> y reinicia el bot.</li>
                </ol>
            )}
            {data?.configured && !data.signals.length && <p className="note">Escuchando. Aún no llegó ningún mensaje.</p>}
            <ul className="tg">
                {(data?.signals || []).map((s, i) => (
                    <li key={i}>
                        <div className="small"><strong>{s.chat}</strong> <span className="dim num">{clock(Date.parse(`${s.created_at}Z`))}</span></div>
                        <p className="msg">{s.text}</p>
                        <span className={`chip ${s.outcome === "abierta" ? "up" : ""}`}>{s.outcome}</span>
                    </li>
                ))}
            </ul>
        </section>
    );
}
