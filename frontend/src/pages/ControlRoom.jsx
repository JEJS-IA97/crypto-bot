import { useState } from "react";

import { getLabLive } from "../api/lab";
import BrainPanel from "../components/room/BrainPanel";
import CandleChart from "../components/room/CandleChart";
import Leaderboard from "../components/room/Leaderboard";
import NowPanel from "../components/room/NowPanel";
import { TelegramFeed, TradeFeed } from "../components/room/SideFeeds";
import TopBar from "../components/room/TopBar";
import usePoll from "../components/room/usePoll";
import Simulation from "./Simulation";

function ControlRoom() {
    const [view, setView] = useState("room");
    const [brain, setBrain] = useState(null);
    const { data: board, error } = usePoll(getLabLive, 10000);

    return (
        <div className="room">
            <TopBar view={view} onView={setView} board={board} />
            {error && <p className="banner">No hay conexión con el bot en 127.0.0.1:8000. ¿Está encendido? ({error})</p>}
            {view === "account" ? (
                <div className="legacy">
                    <Simulation />
                </div>
            ) : (
                <main className="room-grid">
                    <div className="col-main">
                        <CandleChart />
                        <Leaderboard board={board} brain={brain} />
                    </div>
                    <aside className="col-side">
                        <NowPanel board={board} />
                        <BrainPanel onData={setBrain} />
                        <TelegramFeed />
                        <TradeFeed />
                    </aside>
                </main>
            )}
        </div>
    );
}

export default ControlRoom;
