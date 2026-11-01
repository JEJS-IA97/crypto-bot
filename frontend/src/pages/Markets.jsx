import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Ban, Copy, Radar, RefreshCw, Search } from "lucide-react";

import { getActivity, getMarket, getPair } from "../api/lab";
import CandleChart from "../components/room/CandleChart";
import Summary from "../components/room/Summary";
import { clock, coin, price, signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";
import { Badge, Card, Empty, Skeleton } from "../components/ui";

const ICON = { abre: ArrowUpRight, cierra: RefreshCw, copia: Copy, bloqueada: Ban, revision: Radar };

function PairList({ pairs, selected, onSelect }) {
    const [q, setQ] = useState("");
    const list = pairs.filter((p) => coin(p.par).toLowerCase().includes(q.toLowerCase()));
    return (
        <Card className="mk-list" pad={false}>
            <div className="mk-search">
                <label className="sr" htmlFor="mk-q">Buscar par</label>
                <input id="mk-q" placeholder="Buscar par…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            {!pairs.length && <div style={{ padding: 16 }}><Skeleton lines={8} height={30} /></div>}
            {list.map((p) => (
                <button key={p.par} className={`mk-row ${p.par === selected ? "on" : ""}`} onClick={() => onSelect(p.par)}>
                    <span className="mk-ico" aria-hidden="true">{coin(p.par).slice(0, 4)}</span>
                    <span className="mk-name">
                        <strong>{coin(p.par)}</strong>
                        <small>
                            {p.posiciones > 0 ? (
                                <Badge tone={p.lados.includes("SHORT") ? "down" : "up"}>
                                    {p.posiciones} {p.posiciones === 1 ? "posición" : "posiciones"}
                                </Badge>
                            ) : (
                                p.fuente
                            )}
                        </small>
                    </span>
                    <span className="mk-px">
                        <span className="num">{price(p.precio)}</span>
                        <span className={`num ${tone(p.cambio_24h)}`}>{signed(p.cambio_24h, " %")}</span>
                    </span>
                </button>
            ))}
        </Card>
    );
}

function Gauge({ sigma }) {
    if (sigma === null || sigma === undefined) return null;
    const pct = Math.min(Math.abs(sigma) / 3, 1) * 100;
    return (
        <div className="mk-gauge">
            <div className="mk-gauge-top">
                <span>Movimiento de 4 h · la reversión entra a ±3σ</span>
                <span className="num">{signed(sigma)}σ</span>
            </div>
            <div className="mk-gauge-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label="Camino a la señal de reversión">
                <i style={{ width: `${pct}%` }} className={pct >= 100 ? "hot" : pct >= 66 ? "warm" : ""} />
            </div>
            <span className="mk-gauge-top">{pct >= 100 ? "En zona de entrada" : `${Math.round(pct)} % del camino a la señal`}</span>
        </div>
    );
}

function PairDetail({ symbol }) {
    const { data: v } = usePoll(() => getPair(symbol), 10000);
    const ready = v && v.par === symbol;
    const busy = ready ? v.estrategias.filter((e) => !e.estado.startsWith("sin señal")) : [];
    const quiet = ready ? v.estrategias.length - busy.length : 0;
    return (
        <div className="stack">
            <div className="mk-head">
                <h1>{coin(symbol)}<small> / USDT</small></h1>
                {ready ? (
                    <>
                        <span className="px num">{price(v.precio)}</span>
                        <Badge tone={tone(v.cambio_24h)}>{signed(v.cambio_24h, " %")} 24 h</Badge>
                        {v.tendencia && <Badge tone={v.tendencia === "alcista" ? "up" : v.tendencia === "bajista" ? "down" : ""}>Tendencia diaria {v.tendencia}</Badge>}
                        <Badge>{v.regimen}</Badge>
                    </>
                ) : (
                    <div style={{ width: 280 }}><Skeleton lines={1} height={22} /></div>
                )}
            </div>
            <CandleChart symbol={symbol} />
            <div className="cols-2">
                <Card title="Lo que piensa el bot">
                    {!ready ? <Skeleton lines={5} /> : (
                        <>
                            <Gauge sigma={v.movimiento_4h_sigma} />
                            <ul className="mk-strats">
                                {busy.map((e) => (
                                    <li key={e.estrategia}>
                                        <strong>{e.estrategia}</strong>
                                        <Badge>{e.temporalidad}</Badge>
                                        <span>{e.estado}</span>
                                    </li>
                                ))}
                            </ul>
                            {quiet > 0 && <p className="ui-stat-sub">{quiet} estrategias más revisan cada vela y hoy no ven señal.</p>}
                        </>
                    )}
                </Card>
                <Card title={`Posiciones en ${coin(symbol)}`}>
                    {!ready ? <Skeleton lines={3} /> : v.posiciones.length ? (
                        <div className="rows">
                            {v.posiciones.map((p) => (
                                <div className="row" key={p.cuenta}>
                                    <span className={`side-ico ${p.lado === "LONG" ? "up" : "down"}`}>
                                        {p.lado === "LONG" ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
                                    </span>
                                    <div>
                                        <strong>{p.lado === "LONG" ? "Largo" : "Corto"}</strong> · {p.cuenta}
                                        <div className="meta num">entrada {price(p.entrada)}{p.stop ? ` · stop ${price(p.stop)}` : ""}{p.objetivo ? ` · objetivo ${price(p.objetivo)}` : ""}</div>
                                    </div>
                                    <span className={`right num ${tone(p.pnl)}`}>{signed(p.pnl)} USD</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <Empty title="Sin posiciones">El bot entra solo cuando una estrategia da señal y pasa los filtros.</Empty>
                    )}
                </Card>
            </div>
        </div>
    );
}

function Activity() {
    const { data } = usePoll(getActivity, 10000);
    const ev = data?.eventos;
    return (
        <Card title="Actividad en vivo" className="mk-feed" aside={<span className="live-dot on"><i aria-hidden="true" /></span>}>
            {!ev ? <Skeleton lines={6} /> : !ev.length ? (
                <Empty icon={Radar} title="Escuchando el mercado">Cada hora aparece aquí la revisión de todos los pares; las entradas y salidas, al momento.</Empty>
            ) : (
                <ol className="feed scroll-y">
                    {ev.map((e) => {
                        const Icon = ICON[e.tipo] || Radar;
                        return (
                            <li key={`${e.ts}-${e.texto}`} className={e.tipo}>
                                <Icon size={16} aria-hidden="true" />
                                <div>
                                    <time>{clock(e.ts)}</time>
                                    <p>{e.texto}</p>
                                </div>
                            </li>
                        );
                    })}
                </ol>
            )}
        </Card>
    );
}

function Markets({ board }) {
    const { data } = usePoll(getMarket, 10000);
    const [symbol, setSymbol] = useState("BTCUSDT");
    const pairs = useMemo(() => data?.pares || [], [data]);
    return (
        <>
            <Summary board={board} />
            <div className="mk">
                <PairList pairs={pairs} selected={symbol} onSelect={setSymbol} />
                <PairDetail symbol={symbol} />
                <Activity />
            </div>
        </>
    );
}

export default Markets;
