import { getLabTrades, getTelegram } from "../../api/lab";
import { clock, coin, price, signed, tone } from "./fmt";
import usePoll from "./usePoll";

export function TradeFeed() {
    const { data, error } = usePoll(() => getLabTrades(14), 15000);
    return (
        <section className="panel">
            <h2>Últimas operaciones del torneo</h2>
            {error && <p className="note">{error}</p>}
            <div className="feed-scroll">
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
            </div>
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
            {!!data?.channels?.length && (
                <table className="grid compact">
                    <thead>
                        <tr>
                            <th>Canal</th>
                            <th className="r">Señales</th>
                            <th className="r" title="Lo que el propio canal publica">Dice</th>
                            <th className="r" title="Comprobado contra el precio real (solo divisas no OTC, sin gales)">Real</th>
                            <th className="r" title="Resultado apostando 1 USD fijo por señal con pago 85 %">1 USD</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.channels.map((c) => (
                            <tr key={c.chat}>
                                <td className="small">{c.chat}</td>
                                <td className="r num">{c.senales}</td>
                                <td className="r num dim">{c.ganadas}/{c.perdidas}</td>
                                <td className="r num">{c.acierto_real != null ? `${c.acierto_real} % (${c.comprobadas})` : "—"}</td>
                                <td className={`r num ${tone(c.resultado_1usd)}`}>{c.comprobadas ? signed(c.resultado_1usd) : "—"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
            {!!data?.assets?.length && (
                <>
                    <h3>Divisas de las señales y su par en Binance</h3>
                    <div className="feed-scroll">
                        <table className="grid compact">
                            <thead>
                                <tr><th>Activo</th><th className="r">Señales</th><th>En Binance</th></tr>
                            </thead>
                            <tbody>
                                {data.assets.map((a) => (
                                    <tr key={`${a.asset}-${a.otc}`}>
                                        <td>{a.asset}{a.otc && <span className="dim"> OTC</span>}</td>
                                        <td className="r num">{a.senales}</td>
                                        <td className={a.binance ? "up" : "dim"}>{a.binance || "no existe"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
            <ul className="tg tg-scroll">
                {(data?.signals || []).map((s, i) => (
                    <li key={i}>
                        <div className="small"><strong>{s.chat}</strong> <span className="dim num">{clock(Date.parse(`${s.created_at}Z`))}</span></div>
                        <p className="msg">{s.text}</p>
                        <span className={`chip ${s.outcome === "abierta" || s.parsed?.kind === "binaria" ? "up" : ""}`}>{s.outcome}</span>
                        {s.parsed?.verificada && (
                            <span className={`chip ${s.parsed.verificada.result === "gana" ? "up" : s.parsed.verificada.result === "pierde" ? "down" : ""}`}>
                                precio real: {s.parsed.verificada.result}
                            </span>
                        )}
                    </li>
                ))}
            </ul>
        </section>
    );
}
