import { getBrain } from "../../api/lab";
import usePoll from "./usePoll";

function lastLessons(memory) {
    const block = (memory || "").split("\n## ").at(-1) || "";
    const [when, ...lines] = block.split("\n");
    return { when: when.replace(/^#.*$/, "").trim(), items: lines.filter((l) => l.startsWith("- ")).map((l) => l.slice(2)) };
}

function Exam({ m }) {
    const out = m?.examen?.out;
    const live = m?.vivo;
    return (
        <span className="dim small">
            {out ? `examen ${out.net_pnl > 0 ? "+" : ""}${out.net_pnl} USD · PF ${out.profit_factor ?? "—"} · ${out.trades} tr` : ""}
            {live?.trades ? ` · vivo ${live.net_pnl > 0 ? "+" : ""}${live.net_pnl} USD en ${live.trades}` : ""}
        </span>
    );
}

function BrainPanel({ onData }) {
    const { data, error } = usePoll(async () => {
        const next = await getBrain();
        onData?.(next);
        return next;
    }, 30000);
    const live = (data?.genomes || []).filter((g) => g.status === "live" && g.origin !== "fija");
    const rejected = (data?.genomes || []).filter((g) => g.status === "rechazada").slice(0, 25);
    const lessons = lastLessons(data?.memory);
    const c = data?.counts || {};

    return (
        <section className="panel brain">
            <header className="panel-head">
                <h2>Cerebro</h2>
                <span className="dim">
                    {(c.live ?? 0)} operan · {c.banca ?? 0} en banca · {c.retirada ?? 0} retiradas · {c.rechazada ?? 0} rechazadas
                </span>
            </header>
            {error && <p className="note">{error}</p>}
            <h3>Lo último que aprendió {lessons.when && <span className="dim">· {lessons.when}</span>}</h3>
            {lessons.items.length ? (
                <ul className="lessons">
                    {lessons.items.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
            ) : (
                <p className="note">Todavía no hay ciclos de aprendizaje. Corre cada 4 h con BRAIN_ENABLED=true.</p>
            )}
            <h3>Estrategias que creó y aprobó</h3>
            {live.length ? (
                <ul className="genomes">
                    {live.map((g) => (
                        <li key={g.name}>
                            <div>
                                <strong>{g.label}</strong>
                                <span className="tag cerebro">{g.origin}</span>
                                {g.weight > 0 && <span className="dim"> · confianza {(g.weight * 100).toFixed(0)} %</span>}
                            </div>
                            <Exam m={g.metrics} />
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="note">Ninguna ha aprobado el examen fuera de muestra todavía. Es la regla: sin evidencia, no opera.</p>
            )}
            {rejected.length > 0 && (
                <details>
                    <summary>Rechazadas recientes ({c.rechazada})</summary>
                    <ul className="genomes">
                        {rejected.map((g) => (
                            <li key={g.name}>
                                <div>{g.label} <span className="tag">{g.origin}</span></div>
                                <span className="dim">{g.note}</span>
                            </li>
                        ))}
                    </ul>
                </details>
            )}
        </section>
    );
}

export default BrainPanel;
