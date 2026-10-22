import { useMemo, useState } from "react";

import { money, signed, tone } from "./fmt";

const KIND = {
    evo: ["cerebro", "Estrategia creada y aprobada por el cerebro"],
    tg: ["telegram", "Señales de un grupo de Telegram"],
    fija: ["fija", "Estrategia fija del torneo"],
};

const STATUS = {
    live: ["opera", ""],
    banca: ["en la banca", "down"],
    retirada: ["retirada", "down"],
};

function kindOf(name) {
    if (name.startsWith("evo_")) return KIND.evo;
    if (name.startsWith("tg_")) return KIND.tg;
    return KIND.fija;
}

const COLS = [
    ["label", "Estrategia"],
    ["trades", "Trades", "r"],
    ["win_rate", "Acierto %", "r"],
    ["profit_factor", "PF", "r"],
    ["expectancy_r", "Esperanza R", "r"],
    ["fees", "Comisiones", "r"],
    ["net_pnl", "PnL neto", "r"],
    ["return_pct", "Retorno %", "r"],
    ["max_dd_pct", "DD máx %", "r"],
];

function Leaderboard({ board, brain }) {
    const [capital, setCapital] = useState(100);
    const [sort, setSort] = useState(["return_pct", -1]);
    const [showDiscarded, setShowDiscarded] = useState(false);
    const status = useMemo(() => Object.fromEntries((brain?.genomes || []).map((g) => [g.name, g.status])), [brain]);
    const onlyIn = useMemo(
        () => Object.fromEntries((brain?.genomes || []).filter((g) => g.params?.symbols?.length).map((g) => [g.name, g.params.symbols])),
        [brain],
    );
    const discarded = (r) => ["banca", "retirada"].includes(status[r.strategy]);
    const hidden = (board?.rows || []).filter((r) => (capital === 0 || r.capital === capital) && discarded(r)).length;
    const rows = useMemo(() => {
        const list = (board?.rows || []).filter(
            (r) => (capital === 0 || r.capital === capital) && (showDiscarded || !["banca", "retirada"].includes(status[r.strategy])),
        );
        const [key, dir] = sort;
        return [...list].sort((a, b) => {
            const x = a[key] ?? -Infinity;
            const y = b[key] ?? -Infinity;
            return (typeof x === "string" ? x.localeCompare(y) : x - y) * dir;
        });
    }, [board, capital, sort, showDiscarded, status]);

    return (
        <section className="panel">
            <header className="panel-head">
                <h2>Torneo de estrategias <span className="dim">· paper, comisiones reales</span></h2>
                <div className="seg" role="tablist" aria-label="Capital">
                    {[[100, "100 USD"], [50, "50"], [20, "20"], [0, "Todas"]].map(([v, l]) => (
                        <button key={v} role="tab" aria-selected={capital === v} className={capital === v ? "on" : ""} onClick={() => setCapital(v)}>
                            {l}
                        </button>
                    ))}
                </div>
            </header>
            {!rows.length && <p className="note">Aún no hay cuentas con este capital.</p>}
            {hidden > 0 && (
                <p className="foot">
                    {showDiscarded ? "Mostrando" : "Ocultas"} {hidden} estrategias descartadas por el cerebro (quedan guardadas en su memoria).{" "}
                    <button className="link" onClick={() => setShowDiscarded(!showDiscarded)}>
                        {showDiscarded ? "Ocultarlas" : "Verlas"}
                    </button>
                </p>
            )}
            <div className="scroll">
                <table className="grid">
                    <thead>
                        <tr>
                            {COLS.map(([k, label, align]) => (
                                <th key={k} className={align} aria-sort={sort[0] === k ? (sort[1] > 0 ? "ascending" : "descending") : "none"}>
                                    <button onClick={() => setSort([k, sort[0] === k ? -sort[1] : -1])}>{label}</button>
                                </th>
                            ))}
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((r) => {
                            const [kind, kindTitle] = kindOf(r.strategy);
                            const [st, stTone] = STATUS[status[r.strategy] || "live"] || STATUS.live;
                            return (
                                <tr key={`${r.strategy}-${r.capital}`} className={stTone ? "muted" : ""}>
                                    <td>
                                        <span className={`tag ${kind}`} title={kindTitle}>{kind}</span> {r.label}
                                        {capital === 0 && <span className="dim"> · {r.capital}</span>}
                                        {onlyIn[r.strategy] && (
                                            <span className="dim small"> · solo {onlyIn[r.strategy].map((s) => s.replace("USDT", "")).join(", ")}</span>
                                        )}
                                    </td>
                                    <td className="r num">{r.trades}{r.open_positions ? <span className="dim"> +{r.open_positions}</span> : null}</td>
                                    <td className="r num">{r.win_rate ?? "—"}</td>
                                    <td className="r num">{r.profit_factor ?? "—"}</td>
                                    <td className={`r num ${tone(r.expectancy_r)}`}>{r.expectancy_r ?? "—"}</td>
                                    <td className="r num dim">{money(r.fees)}</td>
                                    <td className={`r num ${tone(r.net_pnl)}`}>{signed(r.net_pnl)}</td>
                                    <td className={`r num ${tone(r.return_pct)}`}>{signed(r.return_pct)}</td>
                                    <td className="r num">{r.max_dd_pct}</td>
                                    <td><span className={`chip ${stTone}`}>{st}</span></td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

export default Leaderboard;
