import { ArrowDownRight, ArrowUpRight, Wallet } from "lucide-react";

import api from "../api/client";
import { getLabTrades } from "../api/lab";
import { clock, coin, money, price, signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";
import { Badge, Card, Empty, PageHead, Skeleton, Stat } from "../components/ui";

async function getReal() {
    return (await api.get("/api/lab/real")).data;
}

function RealAccount() {
    const { data } = usePoll(getReal, 30000);
    const bal = data?.saldo;
    const open = Object.entries(data?.abiertas || {});
    const ok = bal && !bal.error;
    return (
        <>
            <div className="real-head">
                <span className={`real-dot ${data?.activo ? "on" : ""}`} />
                <h2>Dinero real · Binance Spot</h2>
                <Badge tone={data?.activo ? "up" : "down"}>{!data ? "…" : data.activo ? "operando" : "apagado"}</Badge>
            </div>
            <Card className="real-card">
                {!data ? <Skeleton lines={3} height={20} /> : (
                    <div className="ui-stats">
                        <Stat big label="Saldo en Binance" value={ok ? `${money(bal.total_usdt)} USDT` : "—"}
                            sub={ok ? `${money(bal.usdt_libre)} USDT libres para operar` : bal?.error || "sin datos"} />
                        <Stat label="Resultado del bot" value={`${signed(data.pnl_total)} USDT`} tone={tone(data.pnl_total)}
                            sub={`${data.operaciones} operaciones · ${data.ganadas || 0} ganadas`} />
                        <Stat label="Abiertas" value={`${open.length} / ${data.max_abiertas}`}
                            sub={`${data.usd_por_operacion} USDT por compra · tope de pérdida ${data.tope_perdida_dia} USDT/día`} />
                    </div>
                )}
            </Card>
            <div className="cols-2">
                <Card title="Compras abiertas y cerradas (reales)">
                    {!data ? <Skeleton lines={3} /> : !open.length && !data.cerradas.length ? (
                        <Empty icon={Wallet} title="Esperando la próxima señal de compra">Solo compra cuando {data.estrategia} da una señal de compra en sus 14 monedas.</Empty>
                    ) : (
                        <div className="rows scroll-y">
                            {open.map(([par, p]) => (
                                <div className="row" key={par}>
                                    <span className="side-ico up"><ArrowUpRight size={18} /></span>
                                    <div><strong>Compra {coin(par)}</strong><div className="meta">abierta · {clock(p.abre)}</div></div>
                                    <span className="right num"><Badge>{money(p.costo)} USDT</Badge></span>
                                </div>
                            ))}
                            {data.cerradas.map((c) => (
                                <div className="row" key={c.cierra}>
                                    <span className={`side-ico ${Number(c.pnl) >= 0 ? "up" : "down"}`}><ArrowUpRight size={18} /></span>
                                    <div><strong>{coin(c.par)}</strong><div className="meta">{c.motivo} · {clock(c.cierra)}</div></div>
                                    <span className={`right num ${tone(c.pnl)}`}>{signed(c.pnl)} USDT</span>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
                <Card title="Tus activos en Binance">
                    {!ok ? <Skeleton lines={3} /> : (
                        <div className="rows">
                            {bal.activos.map((a) => (
                                <div className="row" key={a.activo}>
                                    <div><strong>{a.earn ? a.activo.slice(2) : a.activo}</strong>{a.earn && <span className="meta"> · en Earn</span>}<div className="meta num">{a.cantidad}</div></div>
                                    <span className="right num">{a.usdt != null ? `${money(a.usdt)} USDT` : "—"}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>
            </div>
            <div className="real-head paper"><h2>Simulación (papel)</h2><span className="meta">no usa dinero real</span></div>
        </>
    );
}

async function getCopyTraders() {
    return (await api.get("/api/lab/copytraders")).data;
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
            <PageHead title="Tu cuenta" subtitle="Arriba, lo que el bot hace con tu dinero real en Binance. Abajo, la cuenta de práctica de 40 USD (3x, largo y corto) y los traders copiados en papel." />
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
