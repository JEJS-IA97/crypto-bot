import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../api/lab", () => ({
    getBrain: vi.fn(async () => ({
        counts: { live: 1, banca: 1, retirada: 0, rechazada: 3 },
        memory: "## 2026-10-19 20:38 UTC\n- Aprobada (gemini) tendencia 4h: examen +3.41 USD.",
        genomes: [{ name: "evo_a", label: "tendencia 4h · 34 / 180", origin: "gemini", status: "live", weight: 1, metrics: {} }],
    })),
}));

import BrainPanel from "../BrainPanel";
import Leaderboard from "../Leaderboard";

describe("Sala de control", () => {
    it("el cerebro muestra lo último que aprendió y lo que aprobó", async () => {
        render(<BrainPanel />);
        await waitFor(() => expect(screen.getByText(/examen \+3.41 USD/)).toBeInTheDocument());
        expect(screen.getByText("tendencia 4h · 34 / 180")).toBeInTheDocument();
    });

    it("el ranking marca de dónde viene cada estrategia y cuáles están en la banca", () => {
        const board = {
            rows: [
                { strategy: "orb_ny", label: "ORB", capital: 100, trades: 31, net_pnl: -2, return_pct: -2 },
                { strategy: "tg_1", label: "Telegram · VIP", capital: 100, trades: 2, net_pnl: 1, return_pct: 1 },
            ],
        };
        render(<Leaderboard board={board} brain={{ genomes: [{ name: "orb_ny", status: "banca" }] }} />);
        expect(screen.queryByText("en la banca")).toBeNull(); // descartadas ocultas por defecto
        fireEvent.click(screen.getByText("Verlas"));
        expect(screen.getByText("en la banca")).toBeInTheDocument();
        expect(screen.getByText("telegram")).toBeInTheDocument();
    });
});
