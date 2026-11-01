import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Trophy } from "lucide-react";

import { getLabTrades } from "../api/lab";
import BrainPanel from "../components/room/BrainPanel";
import { OkxFeed, TelegramFeed } from "../components/room/SideFeeds";
import Summary from "../components/room/Summary";
import { clock, coin, price, signed, tone } from "../components/room/fmt";
import usePoll from "../components/room/usePoll";
import { Badge, Card, Empty, PageHead, Skeleton } from "../components/ui";

function kind(name) {
    if (name.startsWith("evo_")) return ["cerebro", "gold"];
    if (name.startsWith("tg_")) return ["telegram", ""];
    if (name.endsWith("_futuros")) return ["futuros", "up"];
    return ["fija", ""];
}

function Ranking({ board, brain }) {
    const [showAll, setShowAll] = useState(false);
    const status = useMemo(() => Object.fromEntries((brain?.genomes || []).map((g) => [g.name, g.status])), [brain]);
    const all = board?.rows;
    const rows = useMemo(
        () => [...(all || [])]
            .filter((r) => showAll || !["banca", "retirada"].includes(status[r.strategy]))
            .sort((a, b) => (b.net_pnl ?? 0) - (a.net_pnl ?? 0)),
        [all, showAll, status],
    );
    const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.net_pnl || 0)));
    const waiting = board?.feed?.waiting || {};
    const champions = new Set(board?.feed?.champions || []);
    return (
        <Card
            title="Clasificación"
            pad={false}
            aside={
                <div className="tabs" role="tablist">
                    <button role="tab" aria-selected={!showAll} className={!showAll ? "on" : ""} onClick={() => setShowAll(false)}>Activas</button>
                    <button role="tab" aria-selected={showAll} className={showAll ? "on" : ""} onClick={() => setShowAll(true)}>Todas</button>
                </div>
            }
        >
            {!all ? <div style={{ padding: 20 }}><Skeleton lines={8} height={24} /></div> : !rows.length ? (
                <Empty icon={Trophy} title="Sin estrategias activas" />
            ) : (
                <ol className="rank">
                    <li className="head">
                        <span>#</span><span>Estrategia</span><span className="n">Operaciones</span><span className="n">Acierto</span>
                        <span className="n hide-md">Retorno</span><span className="n hide-md">Caída máx.</span><span className="n">Ganancia</span>
                    </li>
                    {rows.map((r, i) => {
                        const [k, kt] = kind(r.strategy);
                        return (
                            <li key={`${r.strategy}-${r.capital}`}>
                                <span className="pos">{i + 1}</span>
                                <span className="nm">
                                    <strong title={r.label}>{r.strategy}</strong>
                                    <small>
                                        <Badge tone={kt}>{k}</Badge>{" "}
                                        {champions.has(r.strategy) && <Badge tone="gold">la copia la sigue</Badge>}{" "}
                                        {r.open_positions ? `${r.open_positions} abiertas` : waiting[r.strategy] ? "en espera" : ""}
                                    </small>
                                </span>
                                <span className="n">{r.trades}</span>
                                <span className="n">{r.win_rate != null ? `${r.win_rate} %` : "—"}</span>
                                <span className={`n hide-md ${tone(r.return_pct)}`}>{signed(r.return_pct, " %")}</span>
                                <span className="n hide-md">{r.max_dd_pct} %</span>
                                <span className="n">
                                    <span className={tone(r.net_pnl)}>{signed(r.net_pnl)}</span>
                                    <span className="bar" aria-hidden="true"><i className={r.net_pnl < 0 ? "neg" : ""} style={{ width: `${(Math.abs(r.net_pnl || 0) / maxAbs) * 100}%` }} /></span>
                                </span>
                            </li>
                        );
                    })}
                </ol>
            )}
        </Card>
    );
}

function Trades() {
    const { data } = usePoll(() => getLabTrades(20), 15000);
    return (
        <Card title="Últimas operaciones">
            {!data ? <Skeleton lines={6} /> : !data.length ? <Empty title="Aún sin operaciones" /> : (
                <div className="rows scroll-y">
                    {data.map((t) => (
                        <div className="row" key={t.id}>
                            <span className={`side-ico ${t.side === "LONG" ? "up" : "down"}`}>
                                {t.side === "LONG" ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
                            </span>
                            <div>
                                <strong>{t.side === "LONG" ? "Compra" : "Venta"} {coin(t.symbol)}</strong>
                                <div className="meta">{t.strategy} · {clock(t.closed_ts || t.opened_ts)}</div>
                            </div>
                            <span className="right num">
                                {t.status === "OPEN" ? <Badge>abierta a {price(t.entry)}</Badge> : <span className={tone(t.pnl)}>{signed(t.pnl)} USD</span>}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
}

function Tournament({ board }) {
    const [brain, setBrain] = useState(null);
    return (
        <>
            <PageHead title="Torneo de estrategias" subtitle="Cada estrategia opera con 100 USD de papel y comisiones reales. La que gana con datos pasa a la cuenta de copia." />
            <Summary board={board} />
            <div className="cols-main">
                <div className="stack">
                    <Ranking board={board} brain={brain} />
                    <Trades />
                </div>
                <div className="stack">
                    <BrainPanel onData={setBrain} />
                    <OkxFeed />
                    <TelegramFeed />
                </div>
            </div>
        </>
    );
}

export default Tournament;
