import { getBets, getTelegram } from "../../api/lab";
import { signed, tone } from "./fmt";
import usePoll from "./usePoll";

const STATE = { abierta: "", ganada: "up", perdida: "down", nula: "" };

function BetsView() {
    const { data, error } = usePoll(getBets, 60000);
    const { data: tg } = usePoll(getTelegram, 120000);
    const tipsters = tg?.pronosticos || [];
    return (
        <main className="bets-view">
            <section className="panel">
                <h2>Apuestas deportivas · paper (1 unidad por apuesta)</h2>
                <p className="note">
                    Se comparan tres ideas con dinero ficticio. <strong>Valor</strong>: la mejor cuota paga al menos 2 % más
                    que la cuota justa de la referencia (Pinnacle o Betfair Exchange, sin margen). <strong>Favorito ≤1,30</strong> y{" "}
                    <strong>parley de 3</strong> son las apuestas "seguras", de control. En 23.223 partidos (2019–2026) las seguras
                    perdieron (−1,6 % y −6,8 %) y la de valor ganó (+1,8 %). El CLV dice si tu cuota fue mejor que la de cierre:
                    es la señal de ventaja que no depende de la suerte.
                    {data && !data.odds_api && " Para fútbol de América y NBA falta ODDS_API_KEY (gratis en the-odds-api.com)."}
                </p>
                {error && <p className="note">{error}</p>}
                <table className="grid">
                    <thead>
                        <tr>
                            <th>Estrategia</th>
                            <th className="r">Abiertas</th>
                            <th className="r">Liquidadas</th>
                            <th className="r">Acierto %</th>
                            <th className="r">Cuota media</th>
                            <th className="r">Unidades</th>
                            <th className="r">ROI %</th>
                            <th className="r" title="Promedio de cuánto mejor fue tu cuota que la de cierre">CLV %</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(data?.resumen || []).map((r) => (
                            <tr key={r.strategy}>
                                <td>{r.label}</td>
                                <td className="r num">{r.abiertas}</td>
                                <td className="r num">{r.liquidadas}</td>
                                <td className="r num">{r.acierto ?? "—"}</td>
                                <td className="r num">{r.cuota_media ?? "—"}</td>
                                <td className={`r num ${tone(r.pnl)}`}>{signed(r.pnl)}</td>
                                <td className={`r num ${tone(r.roi)}`}>{r.roi ?? "—"}</td>
                                <td className={`r num ${tone(r.clv_medio)}`}>{r.clv_medio ?? "—"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </section>
            <section className="panel">
                <h2>Pronosticadores de Telegram · seguimiento (1 unidad por pick)</h2>
                <p className="note">
                    El bot guarda cada pick antes del partido y toma el resultado que el propio canal responde (✅/❌).
                    "Sin reportar" alto = el canal esconde sus fallos. Un canal se silencia solo si pierde tras 30 picks
                    o si no reporta más de la mitad.
                </p>
                {!tipsters.length && <p className="note">Todavía no llegaron pronósticos.</p>}
                {!!tipsters.length && (
                    <table className="grid">
                        <thead>
                            <tr>
                                <th>Canal</th>
                                <th className="r">Picks</th>
                                <th className="r">Con resultado</th>
                                <th className="r">Sin reportar</th>
                                <th className="r">Acierto %</th>
                                <th className="r">Cuota media</th>
                                <th className="r">Unidades</th>
                                <th className="r">ROI %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {tipsters.map((t) => (
                                <tr key={t.chat}>
                                    <td>{t.chat}</td>
                                    <td className="r num">{t.picks}</td>
                                    <td className="r num">{t.con_resultado}</td>
                                    <td className="r num">{t.sin_reportar}</td>
                                    <td className="r num">{t.acierto ?? "—"}</td>
                                    <td className="r num">{t.cuota_media ?? "—"}</td>
                                    <td className={`r num ${tone(t.unidades)}`}>{signed(t.unidades)}</td>
                                    <td className={`r num ${tone(t.roi)}`}>{t.roi ?? "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </section>
            <section className="panel">
                <h2>Últimas apuestas</h2>
                {!data?.apuestas?.length && <p className="note">El bot busca partidos de las próximas 48 h cada 6 h.</p>}
                <div className="feed-scroll tall">
                    <table className="grid compact">
                        <tbody>
                            {(data?.apuestas || []).map((b, i) => (
                                <tr key={`${b.partido}-${b.estrategia}-${b.seleccion}-${i}`}>
                                    <td className="dim num">{b.inicio.slice(5, 16).replace("T", " ")}</td>
                                    <td>
                                        {b.partido.split(" + ").map((m) => m.split("|").slice(2, 4).join(" – ")).join(" + ")}
                                        <div className="dim small">
                                            {b.estrategia} · {b.liga} · elige {b.seleccion}
                                            {b.prob_justa ? ` · prob. justa ${(b.prob_justa * 100).toFixed(0)} %` : ""}
                                        </div>
                                    </td>
                                    <td className="r num">{b.cuota.toFixed(2)}</td>
                                    <td className={`r ${STATE[b.estado]}`}>
                                        {b.estado}
                                        {b.pnl != null && <div className="num small">{signed(b.pnl)}</div>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </main>
    );
}

export default BetsView;
