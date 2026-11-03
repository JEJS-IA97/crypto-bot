import { ArrowDownRight, ArrowUpRight, CalendarClock, Wallet } from "lucide-react";

import { getTrend } from "../api/bot";
import api from "../api/client";
import { getLabTrades } from "../api/lab";
import { clock, coin, money, price, signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";
import { Badge, Card, Empty, PageHead, Skeleton, Stat } from "../components/ui";

async function getMainTrades() {
    const accounts = (await api.get("/simulation/accounts")).data;
    if (!accounts?.length) return [];
    return (await api.get(`/simulation/accounts/${accounts[0].id}/trades`)).data;
}

function Track({ dist50, dist200 }) {
    // posición del precio entre −15 % y +15 % de cada media
    const at = (d) => `${Math.max(0, Math.min(100, 50 + Number(d) * (50 / 15)))}%`;
    return (
        <div className="track" aria-hidden="true">
            <b style={{ left: "50%" }}>media</b>
            <i style={{ left: at(dist50), background: "var(--r-accent)" }} title="vs SMA50" />
            <i style={{ left: at(dist200), background: "#64748b" }} title="vs SMA200" />
        </div>
    );
}

function CopyAccount({ board }) {
    const c = board?.balances?.copier;
    const { data: trades } = usePoll(() => getLabTrades(300), 30000);
    const mine = (trades || []).filter((t) => t.strategy === "principal");
    return (
        <>
            <Card>
                {!c ? <Skeleton lines={3} height={20} /> : (
                    <div className="ui-stats">
                        <Stat big label="Saldo actual" value={`${money(c.balance)} USD`} tone={tone(c.balance - c.initial)}
                            sub={`${signed(c.balance - c.initial)} USD desde ${money(c.initial)}`} />
                        <Stat label="Libre" value={money(c.available)} sub={`${c.open_positions} posiciones abiertas`} />
                        <Stat label="Copia a" value={c.copies?.length || 0} sub={c.copies?.join(", ") || "nadie aún"} />
                    </div>
                )}
            </Card>
            <div className="cols-2">
                <Card title="Posiciones abiertas">
                    {!c ? <Skeleton lines={3} /> : !c.positions?.length ? (
                        <Empty icon={Wallet} title="Esperando la próxima señal">Entra cuando una estrategia ganadora abre una operación.</Empty>
                    ) : (
                        <div className="rows">
                            {c.positions.map((p) => (
                                <div className="row" key={p.par}>
                                    <span className={`side-ico ${p.lado === "LONG" ? "up" : "down"}`}>{p.lado === "LONG" ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}</span>
                                    <div>
                                        <strong>{p.lado === "LONG" ? "Largo" : "Corto"} {coin(p.par)}</strong>
                                        <div className="meta num">entrada {price(p.entrada)}{p.stop ? ` · stop ${price(p.stop)}` : ""}{p.objetivo ? ` · objetivo ${price(p.objetivo)}` : ""}</div>
                                        <div className="meta">copiado de {p.fuente} · {clock(p.abierta)}</div>
                                    </div>
                                    <span className={`right num ${tone(p.pnl)}`}>{signed(p.pnl)} USD</span>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
                <Card title="Operaciones copiadas">
                    {!trades ? <Skeleton lines={4} /> : !mine.length ? <Empty title="Aún sin operaciones cerradas" /> : (
                        <div className="rows scroll-y">
                            {mine.map((t) => (
                                <div className="row" key={t.id}>
                                    <span className={`side-ico ${t.side === "LONG" ? "up" : "down"}`}>{t.side === "LONG" ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}</span>
                                    <div><strong>{t.side === "LONG" ? "Largo" : "Corto"} {coin(t.symbol)}</strong><div className="meta">{clock(t.closed_ts || t.opened_ts)}</div></div>
                                    <span className="right num">{t.status === "OPEN" ? <Badge>abierta</Badge> : <span className={tone(t.pnl)}>{signed(t.pnl)} USD</span>}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
            </div>
        </>
    );
}

function MainAccount({ board }) {
    const { data: trend } = usePoll(getTrend, 30000);
    const { data: trades } = usePoll(getMainTrades, 60000);
    const m = board?.balances?.main;
    const feed = board?.feed;
    const fg = feed?.contexto?.fear_greed;
    return (
        <>
            <PageHead
                title="Tu cuenta"
                subtitle="40 USD que copian solo a las estrategias que ya ganaron en vivo (≥5 operaciones con ganancia), en largo y en corto. Debajo, el núcleo de tendencia BTC+ETH, que opera aparte."
            />
            <CopyAccount board={board} />
            <PageHead
                title="Núcleo de tendencia BTC + ETH"
                subtitle="Compra el 50 % del saldo por par cuando el precio cierra sobre su SMA50 y su SMA200; vuelve a USDT cuando cae debajo. Decide una vez al día, por eso pasa semanas quieto."
            />
            <div className="hero">
                <Card>
                    {!m ? <Skeleton lines={3} height={20} /> : (
                        <div className="ui-stats">
                            <Stat label="Saldo" value={`${money(m.balance)} USD`} tone={tone(m.balance - m.initial)}
                                sub={`${signed(m.balance - m.initial)} USD desde ${money(m.initial)}`} />
                            <Stat label="En USDT" value={money(m.available)} sub={`${m.open_positions} posiciones abiertas`} />
                            <Stat label="Próxima compra por par" value={`${money(m.balance * 0.5)} USD`} sub="50 % del saldo" />
                        </div>
                    )}
                </Card>
                <Card title="Contexto del mercado">
                    {!feed ? <Skeleton lines={3} /> : (
                        <div className="ctx">
                            {fg && typeof fg === "object" && <Badge tone={fg.valor < 40 ? "down" : fg.valor > 60 ? "up" : ""}>Miedo y codicia {fg.valor} · {fg.texto}</Badge>}
                            {feed.macro?.bloqueo ? <Badge tone="down">Pausa macro: {feed.macro.bloqueo}</Badge>
                                : feed.macro?.proximo && <Badge>{feed.macro.proximo.evento} en {Math.round(feed.macro.proximo.horas)} h</Badge>}
                            <Badge tone={feed.btc_ok ? "up" : "down"}>BTC {feed.btc_ok ? "sobre" : "bajo"} su SMA20</Badge>
                            {trend?.next_decision_utc && (
                                <Badge><CalendarClock size={12} aria-hidden="true" /> Decide {new Date(`${trend.next_decision_utc}Z`).toLocaleString("es-VE", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })}</Badge>
                            )}
                        </div>
                    )}
                </Card>
            </div>
            <div className="pair-trend">
                {!trend ? [0, 1].map((i) => <div className="pt" key={i}><Skeleton lines={4} /></div>) : trend.pairs.map((p) => (
                    <article className="pt" key={p.symbol}>
                        <div className="pt-top">
                            <strong>{coin(p.symbol)}</strong>
                            <Badge tone={p.signal === "DENTRO" ? "up" : "down"}>{p.signal === "DENTRO" ? "Comprado" : "En USDT"}</Badge>
                        </div>
                        <span className="num" style={{ fontSize: 22, fontWeight: 600 }}>{price(feed?.prices?.[p.symbol] ?? p.close)}</span>
                        <Track dist50={p.dist_fast_pct} dist200={p.dist_slow_pct} />
                        <div className="ui-stat-sub">
                            <span className={tone(Number(p.dist_fast_pct))}>{signed(Number(p.dist_fast_pct), " %")}</span> vs SMA50 ·{" "}
                            <span className={tone(Number(p.dist_slow_pct))}>{signed(Number(p.dist_slow_pct), " %")}</span> vs SMA200
                        </div>
                        <p style={{ margin: 0 }}>{p.signal === "DENTRO" ? "Tendencia a favor: mantiene la compra." : `Para comprar, el precio debe subir ${Math.abs(Number(p.dist_fast_pct)).toFixed(1)} % y cerrar el día sobre su SMA50.`}</p>
                    </article>
                ))}
            </div>
            <Card title="Historial de operaciones">
                {!trades ? <Skeleton lines={5} /> : !trades.length ? <Empty icon={Wallet} title="Sin operaciones todavía" /> : (
                    <div className="rows">
                        {trades.slice(0, 30).map((t) => (
                            <div className="row" key={t.id}>
                                <span className={`side-ico ${t.side === "BUY" ? "up" : "down"}`}>{t.side === "BUY" ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}</span>
                                <div>
                                    <strong>{t.side === "BUY" ? "Compra" : "Venta"} {coin(t.symbol)}</strong>
                                    <div className="meta num">{money(t.total_usd)} USD a {price(t.price)} · {clock(Date.parse(`${t.executed_at}Z`))}</div>
                                </div>
                                <span className={`right num ${tone(Number(t.realized_pnl_usd))}`}>{Number(t.realized_pnl_usd) ? `${signed(Number(t.realized_pnl_usd))} USD` : "—"}</span>
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        </>
    );
}

export default MainAccount;
