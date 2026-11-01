import { useEffect, useState } from "react";

import { getLabLive } from "../api/lab";
import Shell from "../components/room/Shell";
import usePoll from "../components/room/usePoll";
import Bets from "./Bets";
import MainAccount from "./MainAccount";
import Markets from "./Markets";
import Tournament from "./Tournament";

const PAGES = { market: Markets, room: Tournament, account: MainAccount, bets: Bets };

function readView() {
    const v = window.location.hash.slice(1);
    return PAGES[v] ? v : "market";
}

function ControlRoom() {
    const [view, setView] = useState(readView);
    const { data: board, error } = usePoll(getLabLive, 10000);
    useEffect(() => {
        const onHash = () => setView(readView());
        window.addEventListener("hashchange", onHash);
        return () => window.removeEventListener("hashchange", onHash);
    }, []);
    const go = (v) => {
        window.location.hash = v;
        setView(v);
    };
    const Page = PAGES[view];
    return (
        <Shell view={view} onView={go} board={board}>
            {error && !board && <p className="banner">No hay conexión con el bot en 127.0.0.1:8000. ¿Está encendido?</p>}
            <Page board={board} />
        </Shell>
    );
}

export default ControlRoom;
