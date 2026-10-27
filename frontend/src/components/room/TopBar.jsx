import { useState } from "react";
import { Pause, Play, Radio } from "lucide-react";

import { getBotStatus, startBot, stopBot } from "../../api/bot";
import { setToken } from "../../api/client";
import { money, signed, tone } from "./fmt";
import usePoll from "./usePoll";

function TopBar({ view, onView, board }) {
    const { data: status } = usePoll(getBotStatus, 10000);
    const [busy, setBusy] = useState(false);
    const [needToken, setNeedToken] = useState(false);
    const [msg, setMsg] = useState("");
    const rows = board?.rows || [];
    const net = rows.reduce((a, r) => a + (r.net_pnl || 0), 0);
    const open = rows.reduce((a, r) => a + (r.open_positions || 0), 0);
    const trades = rows.reduce((a, r) => a + (r.trades || 0), 0);
    const feed = board?.feed;
    const running = status?.running;

    const toggle = async () => {
        setBusy(true);
        setMsg("");
        try {
            await (running ? stopBot() : startBot());
            setMsg(running ? "Bot detenido: no abre operaciones nuevas." : "Bot en marcha.");
        } catch (err) {
            if (err?.response?.status === 401) setNeedToken(true);
            else setMsg("No pude cambiar el estado del bot.");
        } finally {
            setBusy(false);
        }
    };

    return (
        <header className="topbar">
            <div className="brand">
                <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width="20" height="20" />
                <strong>crypto-bot</strong>
                <span className="badge">{status?.fase || "…"}</span>
            </div>
            <nav className="views" aria-label="Vistas">
                <button className={view === "room" ? "on" : ""} onClick={() => onView("room")}>Sala de control</button>
                <button className={view === "account" ? "on" : ""} onClick={() => onView("account")}>Cuenta principal</button>
                <button className={view === "bets" ? "on" : ""} onClick={() => onView("bets")}>Apuestas</button>
            </nav>
            <dl className="stats">
                <div>
                    <dt>Torneo, PnL neto</dt>
                    <dd className={`num ${tone(net)}`}>{signed(net)} USD</dd>
                </div>
                <div>
                    <dt>Operaciones</dt>
                    <dd className="num">{trades} · {open} abiertas</dd>
                </div>
                <div>
                    <dt>Datos</dt>
                    <dd className={feed?.connected ? "live" : "down"}>
                        <Radio size={14} strokeWidth={1.75} aria-hidden="true" />
                        {feed?.connected ? "En vivo" : "Sin feed"}
                    </dd>
                </div>
            </dl>
            <div className="actions">
                {needToken && (
                    <form
                        className="token"
                        onSubmit={(e) => {
                            e.preventDefault();
                            setToken(new FormData(e.currentTarget).get("t"));
                            setNeedToken(false);
                            toggle();
                        }}
                    >
                        <label>
                            <span className="sr">Token de la API</span>
                            <input name="t" type="password" placeholder="API_TOKEN del .env" autoFocus />
                        </label>
                        <button type="submit">Guardar</button>
                    </form>
                )}
                {msg && <span className="dim">{msg}</span>}
                <button className={`kill ${running ? "" : "resume"}`} onClick={toggle} disabled={busy || !status}>
                    {running ? <Pause size={15} strokeWidth={1.75} /> : <Play size={15} strokeWidth={1.75} />}
                    {running ? "Detener bot" : "Reanudar bot"}
                </button>
            </div>
            <span className="sr" aria-live="polite">{money(net)}</span>
        </header>
    );
}

export default TopBar;
