import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DecisionInspector from "../DecisionInspector";
import {
    getDecisionReplay,
    getDecisionWhy,
    getDecisions,
} from "../../api/bot";

vi.mock("../../api/bot", () => ({
    getDecisionWhy: vi.fn(),
    getDecisionReplay: vi.fn(),
    getDecisions: vi.fn(),
}));

const DECISIONES = {
    decisiones: [
        {
            id: 7,
            symbol: "BTCUSDT",
            side: "BUY",
            status: "CLOSED",
            pnl_usd: "0.1798",
            created_at: "2026-10-07T12:00:00Z",
        },
        {
            id: 8,
            symbol: "ETHUSDT",
            side: "BUY",
            status: "OPENED",
            pnl_usd: null,
            created_at: "2026-10-07T13:00:00Z",
        },
    ],
};

const WHY = {
    decision: { id: 7, symbol: "BTCUSDT", side: "BUY", status: "CLOSED" },
    factors: { positive: ["Cruce alcista"], negative: [], indicators: {} },
    ai: null,
    risk: null,
    outcome: { status: "CLOSED", pnl_usd: "0.1798" },
    unavailable: [],
};

const REPLAY = {
    decision: { id: 7, symbol: "BTCUSDT", side: "BUY", status: "CLOSED" },
    snapshot: {
        price: "100",
        timestamp: null,
        indicators: {},
        candles: [],
        config: {},
        correlation_id: "corr-7",
    },
    events: [],
    ai_evaluation: null,
    position: null,
    outcome: {
        status: "CLOSED",
        pnl_usd: "0.1798",
        filled_at: null,
        closed_at: null,
    },
    unavailable: [],
};

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("DecisionInspector (spec 009, RF-4/5/6)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getDecisions.mockResolvedValue(DECISIONES);
        getDecisionWhy.mockResolvedValue(WHY);
        getDecisionReplay.mockResolvedValue(REPLAY);
    });

    afterEach(cleanup);

    it("lista las decisiones recientes y muestra el panel vacío", async () => {
        render(<DecisionInspector />);

        await screen.findByTestId("decision-inspector");
        expect(
            screen.getByText("Selecciona una decisión para inspeccionarla.")
        ).toBeInTheDocument();

        const select = screen.getByLabelText(
            "Decisión a inspeccionar"
        );
        expect(select).toHaveValue("");
        expect(
            screen.getByRole("option", {
                name: "#7 · BTCUSDT · BUY",
            })
        ).toBeInTheDocument();
        expect(
            screen.getByRole("option", {
                name: "#8 · ETHUSDT · BUY",
            })
        ).toBeInTheDocument();
    });

    it("al elegir una decisión carga Why?, replay y timeline", async () => {
        render(<DecisionInspector />);
        await screen.findByTestId("decision-inspector");

        fireEvent.change(
            screen.getByLabelText("Decisión a inspeccionar"),
            { target: { value: "7" } }
        );

        await screen.findByTestId("why-panel");
        expect(screen.getByTestId("replay-view")).toBeInTheDocument();
        expect(
            screen.getByTestId("decision-timeline-7")
        ).toBeInTheDocument();

        expect(getDecisionWhy).toHaveBeenCalledWith(7);
        expect(getDecisionReplay).toHaveBeenCalledWith(7);
    });

    it("acepta una decisión preseleccionada desde fuera (marcador)", async () => {
        render(<DecisionInspector selectedDecisionId={8} />);
        await flushPromises();

        await screen.findByTestId("why-panel");
        expect(getDecisionWhy).toHaveBeenCalledWith(8);
        expect(
            screen.getByLabelText("Decisión a inspeccionar")
        ).toHaveValue("8");
    });
});
