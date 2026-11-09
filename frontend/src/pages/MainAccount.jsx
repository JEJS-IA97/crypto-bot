import api from "../api/client";
import { getLabTrades } from "../api/lab";
import { clock, coin, money, price, signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";
import { Badge, Card, Empty, PageHead, Skeleton, Stat } from "../components/ui";

async function getReal() {
    return (await api.get("/lab/real")).data;
}

function RealAccount() {
    const { data } = usePoll(getReal, 30000);
    if (!data) return <Card title="Dinero real en Binance"><Skeleton lines={3} /></Card>;
    const open = Object.entries(data.abiertas || {});
    return (
        <Card title={`Dinero real en Binance ${data.activo ? "· activo" : "· apagado"}`}>
            <div className="meta">Solo compras de {data.estrategia}, {data.usd_por_operacion} USD por operación, máximo {data.max_abiertas} abiertas; deja de comprar si pierde {data.tope_perdida_dia} USD en el día.</div>
            <div className="meta num">{data.operaciones} cerradas · resultado <span className={tone(data.pnl_total)}>{signed(data.pnl_total)} USDT</span></div>
            <div className="rows">
                {open.map(([par, p]) => (
                    <div className="row" key={par}><div><strong>Compra {coin(par)}</strong><div className="meta">{clock(p.abre)}</div></div><span className="right num">{money(p.costo)} USDT</span></div>
                ))}
                {data.cerradas.map((c) => (
                    <div className="row" key={c.cierra}><div><strong>{coin(c.par)}</strong><div className="meta">{c.motivo} · {clock(c.cierra)}</div></div><span className={`right num ${tone(c.pnl)}`}>{signed(c.pnl)} USDT</span></div>
                ))}
                {!open.length && !data.cerradas.length && <Empty title="Esperando la próxima señal de compra" />}
            </div>
        </Card>
    );
}

async function getCopyTraders() {
    return (await api.get("/lab/copytraders")).data;
}

function CopyTraders() {
    const { data } = usePoll(getCopyTraders, 60000);
    const list = data?.traders || [];
    return (
        <Card title="Traders de Binance copiados en papel">
            {!data ? <Skeleton lines={5} /> : !list.length ? <Empty title="Esperando su primera operación cerrada desde hoy" /> : (
                <div className="rows">
                    {list.map((t) => (
                        <div className="row" key={t.id}>
                            <div>
                                <strong>{t.nombre}</strong> {t.banca && <Badge tone="down">en la banca</Badge>}
                                <div className="meta num">
                                    {t.copias} copias{t.acierto != null ? ` · acierto ${t.acierto} %` : ""}
                                    {t.ultimas?.[0] ? ` · última: ${t.ultimas[0].lado} ${coin(t.ultimas[0].par)} ${signed(t.ultimas[0].pnl)} USD` : ""}
                                </div>
                            </div>
                            <span className={`right num ${tone(t.saldo - data.capital)}`}>{money(t.saldo)} USD</span>
                        </div>
                    ))}
                </div>
            )}
        </Card>
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
    const feed = board?.feed;
    const fg = feed?.contexto?.fear_greed;
    return (
        <>
            <PageHead
                title="Tu cuenta"
                subtitle="40 USD que copian solo a las estrategias que ya ganaron en vivo (≥5 operaciones con ganancia), en largo y en corto, a 3x."
            />
            <RealAccount />
            <CopyAccount board={board} />
            <CopyTraders />
            <div className="hero">
                <Card title="Contexto del mercado">
                    {!feed ? <Skeleton lines={3} /> : (
                        <div className="ctx">
                            {fg && typeof fg === "object" && <Badge tone={fg.valor < 40 ? "down" : fg.valor > 60 ? "up" : ""}>Miedo y codicia {fg.valor} · {fg.texto}</Badge>}
                            {feed.macro?.bloqueo ? <Badge tone="down">Pausa macro: {feed.macro.bloqueo}</Badge>
                                : feed.macro?.proximo && <Badge>{feed.macro.proximo.evento} en {Math.round(feed.macro.proximo.horas)} h</Badge>}
                            <Badge tone={feed.btc_ok ? "up" : "down"}>BTC {feed.btc_ok ? "sobre" : "bajo"} su SMA20</Badge>
                        </div>
                    )}
                </Card>
            </div>
        </>
    );
}

export default MainAccount;
