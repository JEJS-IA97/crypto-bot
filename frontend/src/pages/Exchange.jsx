import { useState } from "react";

import { getActivity, getMarket, getPair } from "../api/lab";
import Balances from "../components/room/Balances";
import CandleChart from "../components/room/CandleChart";
import { clock, coin, price, signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";

const KIND = { abre: "Abrió", cierra: "Cerró", copia: "Copia", bloqueada: "Bloqueada", revision: "Revisión" };

function PairList({ pairs, selected, onSelect }) {
    return (
        <nav className="ex-list" aria-label="Pares">
            <div className="ex-list-head">
                <span>Par</span>
                <span>Precio</span>
                <span>24 h</span>
            </div>
            {pairs.map((p) => (
                <button key={p.par} className={`ex-row ${p.par === selected ? "on" : ""}`} onClick={() => onSelect(p.par)}>
                    <span className="ex-coin">
                        <strong>{coin(p.par)}</strong>
                        {p.posiciones > 0 ? (
                            <em className={`pill ${p.lados.includes("SHORT") ? "down" : "up"}`}>
                                {p.lados.map((l) => (l === "LONG" ? "▲" : "▼")).join("")} {p.posiciones}
                            </em>
                        ) : (
                            <small>{p.fuente}</small>
                        )}
                    </span>
                    <span className="num">{price(p.precio)}</span>
                    <span className={`num ${tone(p.cambio_24h)}`}>{signed(p.cambio_24h, " %")}</span>
                </button>
            ))}
        </nav>
    );
}

function Gauge({ sigma }) {
    if (sigma === null || sigma === undefined) return null;
    const pct = Math.min(Math.abs(sigma) / 3, 1) * 100;
    return (
        <div className="ex-gauge" title="La reversión de 4 h entra cuando el movimiento llega a ±3σ">
            <div className="ex-gauge-bar">
                <i style={{ width: `${pct}%` }} className={pct >= 100 ? "hot" : pct >= 66 ? "warm" : ""} />
            </div>
            <span className="num">
                {signed(sigma)}σ de 3σ · {pct >= 100 ? "zona de entrada" : `${Math.round(pct)} % del camino`}
            </span>
        </div>
    );
}

function PairDetail({ symbol }) {
    const { data: v } = usePoll(() => getPair(symbol), 10000);
    if (!v || v.par !== symbol) return <section className="panel ex-detail"><p className="dim">Cargando {coin(symbol)}…</p></section>;
    const busy = v.estrategias.filter((e) => !e.estado.startsWith("sin señal"));
    const quiet = v.estrategias.length - busy.length;
    return (
        <section className="ex-detail">
            <header className="ex-quote">
                <h1>{coin(symbol)}<small>/USDT</small></h1>
                <span className="num big">{price(v.precio)}</span>
                <span className={`num ${tone(v.cambio_24h)}`}>{signed(v.cambio_24h, " %")} 24 h</span>
                <span className="tag">Tendencia diaria: {v.tendencia || "—"}</span>
                <span className="tag">{v.regimen}</span>
            </header>
            <CandleChart symbol={symbol} />
            <div className="ex-cards">
                <article className="panel">
                    <h2>Lo que piensa el bot</h2>
                    <Gauge sigma={v.movimiento_4h_sigma} />
                    <ul className="ex-think">
                        {busy.map((e) => (
                            <li key={e.estrategia}>
                                <strong>{e.estrategia}</strong> <span className="dim">{e.temporalidad}</span>
                                <span>{e.estado}</span>
                            </li>
                        ))}
                        {quiet > 0 && <li className="dim">{quiet} estrategias más revisan cada vela y no ven señal.</li>}
                    </ul>
                </article>
                <article className="panel">
                    <h2>Posiciones abiertas en {coin(symbol)}</h2>
                    {v.posiciones.length ? (
                        <ul className="ex-pos">
                            {v.posiciones.map((p) => (
                                <li key={p.cuenta}>
                                    <span className={p.lado === "LONG" ? "up" : "down"}>{p.lado === "LONG" ? "▲ Largo" : "▼ Corto"}</span>
                                    <span>{p.cuenta}</span>
                                    <span className="num">entrada {price(p.entrada)}</span>
                                    <span className={`num ${tone(p.pnl)}`}>{signed(p.pnl)} USD</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="dim">Ninguna. El bot entra solo cuando una estrategia da señal y pasa los filtros.</p>
                    )}
                </article>
            </div>
        </section>
    );
}

function Activity() {
    const { data } = usePoll(getActivity, 10000);
    const ev = data?.eventos || [];
    return (
        <aside className="panel ex-activity" aria-label="Actividad">
            <h2>Actividad en vivo</h2>
            {!ev.length && <p className="dim">Aún sin eventos desde el último arranque. Cada hora aparece la revisión de todos los pares.</p>}
            <ol>
                {ev.map((e) => (
                    <li key={`${e.ts}-${e.texto}`} className={`ev-${e.tipo}`}>
                        <time>{clock(e.ts)}</time>
                        <b>{KIND[e.tipo] || e.tipo}</b>
                        <p>{e.texto}</p>
                    </li>
                ))}
            </ol>
        </aside>
    );
}

function Exchange({ board }) {
    const { data } = usePoll(getMarket, 10000);
    const [symbol, setSymbol] = useState("BTCUSDT");
    const pairs = data?.pares || [];
    return (
        <div className="exchange">
            <Balances board={board} />
            <div className="ex-grid">
                <PairList pairs={pairs} selected={symbol} onSelect={setSymbol} />
                <PairDetail symbol={symbol} />
                <Activity />
            </div>
        </div>
    );
}

export default Exchange;
