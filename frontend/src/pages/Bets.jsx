import { useState } from "react";
import { CheckCircle2, CircleDashed, Ticket, XCircle } from "lucide-react";

import { getBets, getTelegram } from "../api/lab";
import { signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";
import { Badge, Card, Empty, PageHead, Skeleton } from "../components/ui";

const MARKET = {
    "goles_o0.5": "Más de 0,5 goles", "goles_o1.5": "Más de 1,5 goles", "goles_u3.5": "Menos de 3,5 goles", "goles_u4.5": "Menos de 4,5 goles",
    gol_1t: "Gol en el 1.er tiempo", local_marca: "Marca el local", visita_marca: "Marca el visitante",
    "corners_o6.5": "Más de 6,5 córners", "corners_o7.5": "Más de 7,5 córners", "corners_u13.5": "Menos de 13,5 córners",
    "tarjetas_o1.5": "Más de 1,5 tarjetas", "tarjetas_o2.5": "Más de 2,5 tarjetas", "tarjetas_u6.5": "Menos de 6,5 tarjetas",
    "faltas_o18.5": "Más de 18,5 faltas", H: "Gana el local", D: "Empate", A: "Gana el visitante",
};
const SHORT = { seguro: "Seguras", parley_seguro: "Parley de seguras", valor: "Valor", favorito_130: "Favorito ≤1,30", parley3_130: "Parley de favoritos" };
const FILTERS = [["todas", "Todas"], ["seguro", "Seguras"], ["parley_seguro", "Parleys"], ["valor", "Valor"], ["favorito_130", "Favoritos"]];

const teams = (key) => key.split("|").slice(2, 4).join(" – ");
const pick = (s) => s.split(",").map((x) => MARKET[x] || x);

function StatusIcon({ estado }) {
    if (estado === "ganada") return <CheckCircle2 size={18} className="up" aria-label="ganada" />;
    if (estado === "perdida") return <XCircle size={18} className="down" aria-label="perdida" />;
    return <CircleDashed size={18} className="dim" aria-label={estado} />;
}

function Bets() {
    const { data } = usePoll(getBets, 60000);
    const { data: tg } = usePoll(getTelegram, 120000);
    const [filter, setFilter] = useState("todas");
    const bets = (data?.apuestas || []).filter((b) => filter === "todas" || b.estrategia === filter);
    const tipsters = tg?.pronosticos || [];
    return (
        <>
            <PageHead
                title="Apuestas deportivas"
                subtitle="Todo en papel, 1 unidad por apuesta. Las seguras (goles, córners, tarjetas, faltas) aciertan ~92 % en la prueba histórica; solo dan ganancia si la casa paga más que la cuota mínima."
            />
            <div className="bet-cards">
                {!data ? [0, 1, 2, 3, 4].map((i) => <div className="bet-card" key={i}><Skeleton lines={4} /></div>) : data.resumen.map((r) => (
                    <article className="bet-card" key={r.strategy}>
                        <h3>{SHORT[r.strategy] || r.strategy}</h3>
                        <p>{r.label}</p>
                        <dl>
                            <div><dt>Abiertas</dt><dd>{r.abiertas}</dd></div>
                            <div><dt>Liquidadas</dt><dd>{r.liquidadas}</dd></div>
                            <div><dt>Acierto</dt><dd>{r.acierto != null ? `${r.acierto} %` : "—"}</dd></div>
                            <div><dt>Unidades</dt><dd className={tone(r.pnl)}>{signed(r.pnl)}</dd></div>
                        </dl>
                    </article>
                ))}
            </div>
            <div className="cols-main">
                <Card
                    title="Apuestas"
                    aside={
                        <div className="tabs" role="tablist" aria-label="Filtrar">
                            {FILTERS.map(([k, l]) => (
                                <button key={k} role="tab" aria-selected={filter === k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{l}</button>
                            ))}
                        </div>
                    }
                >
                    {!data ? <Skeleton lines={8} height={20} /> : !bets.length ? (
                        <Empty icon={Ticket} title="Nada en este filtro">El bot busca partidos de las próximas 48 h cada 6 h y liquida cuando se publican los resultados.</Empty>
                    ) : (
                        <div className="rows scroll-y" style={{ maxHeight: 640 }}>
                            {bets.map((b, i) => (
                                <div className="row" key={`${b.partido}-${b.estrategia}-${b.seleccion}-${i}`}>
                                    <StatusIcon estado={b.estado} />
                                    <div>
                                        <strong>{b.partido.split(" + ").map(teams).join(" · ")}</strong>
                                        <div className="meta">
                                            {pick(b.seleccion).join(" + ")} · {SHORT[b.estrategia] || b.estrategia}
                                            {b.prob_justa ? ` · prob. ${(b.prob_justa * 100).toFixed(0)} %` : ""} · {b.inicio.slice(5, 16).replace("T", " ")}
                                        </div>
                                    </div>
                                    <div className="right">
                                        <div className="num">@{b.cuota.toFixed(2)}</div>
                                        {b.pnl != null ? <span className={`num ${tone(b.pnl)}`}>{signed(b.pnl)}</span> : <span className="meta">{b.estado}</span>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
                <div className="stack">
                    <Card title="Cómo leerlo">
                        <ul className="mk-strats">
                            <li><strong>Seguras</strong><span>Mercado con ≥85 % de probabilidad según el historial de ambos equipos. La cuota que ves es la mínima que hay que exigirle a la casa.</span></li>
                            <li><strong>Valor</strong><span>La mejor casa paga más que la cuota justa de Pinnacle: la única que ganó en la prueba de 23.223 partidos.</span></li>
                            <li><strong>Favoritos</strong><span>Control: favoritos ≤1,30. Aciertan mucho pero históricamente pierden por el margen de la casa.</span></li>
                        </ul>
                    </Card>
                    <Card title="Pronosticadores de Telegram">
                        {!tg ? <Skeleton lines={3} /> : !tipsters.length ? (
                            <Empty title="Sin picks todavía">Gainblers sigue pendiente de aprobar la entrada.</Empty>
                        ) : (
                            <div className="rows">
                                {tipsters.map((t) => (
                                    <div className="row" key={t.chat}>
                                        <Badge>{t.picks}</Badge>
                                        <div><strong>{t.chat}</strong><div className="meta">{t.con_resultado} con resultado · {t.sin_reportar} sin reportar</div></div>
                                        <span className={`right num ${tone(t.roi)}`}>{t.roi != null ? `${t.roi} %` : "—"}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Card>
                </div>
            </div>
        </>
    );
}

export default Bets;
