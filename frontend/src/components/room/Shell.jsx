import { useState } from "react";
import { CandlestickChart, Pause, Play, Ticket, Trophy, Wallet } from "lucide-react";

import { getBotStatus, startBot, stopBot } from "../../api/bot";
import { setToken } from "../../api/client";
import { Badge } from "../ui";
import usePoll from "./usePoll";

export const VIEWS = [
    ["market", "Mercados", CandlestickChart],
    ["room", "Torneo", Trophy],
    ["account", "Cuenta principal", Wallet],
    ["bets", "Apuestas", Ticket],
];

function Shell({ view, onView, board, children }) {
    const { data: status } = usePoll(getBotStatus, 10000);
    const [busy, setBusy] = useState(false);
    const [needToken, setNeedToken] = useState(false);
    const running = status?.running;
    const live = board?.feed?.seconds_since_tick != null && board.feed.seconds_since_tick < 120;

    const toggle = async () => {
        setBusy(true);
        try {
            await (running ? stopBot() : startBot());
        } catch (err) {
            if (err?.response?.status === 401) setNeedToken(true);
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="room app">
            <aside className="side">
                <div className="side-brand">
                    <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width="22" height="22" />
                    <strong>crypto-bot</strong>
                    <Badge tone="gold">{status?.fase || "…"}</Badge>
                </div>
                <nav aria-label="Vistas">
                    {VIEWS.map(([key, label, Icon]) => (
                        <button key={key} className={view === key ? "on" : ""} onClick={() => onView(key)} aria-current={view === key ? "page" : undefined}>
                            <Icon size={18} strokeWidth={1.75} aria-hidden="true" />
                            <span>{label}</span>
                        </button>
                    ))}
                </nav>
                <div className="side-foot">
                    <span className={`live-dot ${live ? "on" : ""}`}>
                        <i aria-hidden="true" />
                        {live ? "Precios en vivo" : board ? "Reconectando precios…" : "Conectando…"}
                    </span>
                    {needToken && (
                        <form
                            onSubmit={(e) => {
                                e.preventDefault();
                                setToken(new FormData(e.currentTarget).get("t"));
                                setNeedToken(false);
                                toggle();
                            }}
                        >
                            <input name="t" type="password" placeholder="API_TOKEN del .env" aria-label="Token de la API" autoFocus />
                        </form>
                    )}
                    <button className={`kill-btn ${running ? "" : "resume"}`} onClick={toggle} disabled={busy || !status}>
                        {running ? <Pause size={15} strokeWidth={1.75} /> : <Play size={15} strokeWidth={1.75} />}
                        {!status ? "…" : running ? "Detener bot" : "Reanudar bot"}
                    </button>
                </div>
            </aside>
            <main className="main">{children}</main>
        </div>
    );
}

export default Shell;
