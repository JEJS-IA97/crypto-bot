import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WhyPanel from "../WhyPanel";
import { getDecisionWhy } from "../../api/bot";

vi.mock("../../api/bot", () => ({
    getDecisionWhy: vi.fn(),
    getDecisionReplay: vi.fn(),
    getDecisions: vi.fn(),
}));

const WHY_FULL = {
    decision: {
        id: 7,
        symbol: "BTCUSDT",
        side: "BUY",
        status: "CLOSED",
        rejection_reason: null,
        quantity: "0.1",
        price: "100",
        stop_price: "98",
        take_profit_price: "102",
        pnl_usd: "0.1798",
        created_at: "2026-10-07T12:00:00Z",
        filled_at: "2026-10-07T12:00:02Z",
        closed_at: "2026-10-07T13:00:00Z",
    },
    factors: {
        positive: ["Cruce alcista", "RSI en zona neutra"],
        negative: ["Volumen bajo"],
        indicators: {
            ema_short: "101.5",
            ema_long: "99.25",
            rsi: "63.4",
        },
    },
    ai: {
        decision: "BUY",
        direction: "long",
        confidence: "0.72",
        model: "gpt-4o-mini",
        prompt_version: "v3",
        latency_ms: 850,
        cost_usd: "0.0012",
        risk_flags: ["bajo_volumen"],
        created_at: "2026-10-07T12:00:01Z",
    },
    risk: {
        action: "ALLOW",
        reason: null,
        requested_usd: "10",
        allowed_usd: "10",
        committed_usd: "10",
        open_positions: 1,
    },
    outcome: {
        status: "CLOSED",
        pnl_usd: "0.1798",
    },
    unavailable: [],
};

const WHY_MINIMAL = {
    decision: {
        id: 9,
        symbol: "ETHUSDT",
        side: "BUY",
        status: "PENDING",
        rejection_reason: null,
        quantity: "0.5",
        price: "50",
        stop_price: null,
        take_profit_price: null,
        pnl_usd: null,
        created_at: "2026-10-07T14:00:00Z",
        filled_at: null,
        closed_at: null,
    },
    factors: {
        positive: [],
        negative: [],
        indicators: {},
    },
    ai: null,
    risk: null,
    outcome: {
        status: "PENDING",
        pnl_usd: null,
    },
    unavailable: [
        {
            section: "ai",
            reason: "sin correlation_id en el snapshot",
        },
        {
            section: "risk",
            reason: "sin correlation_id en el snapshot",
        },
    ],
};

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("WhyPanel (spec 009, RF-4)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getDecisionWhy.mockResolvedValue(WHY_FULL);
    });

    afterEach(cleanup);

    it("muestra los factores IA y los indicadores crudos del snapshot", async () => {
        render(<WhyPanel decisionId={7} />);

        const panel = await screen.findByTestId("why-panel");
        expect(panel).toHaveTextContent("Cruce alcista");
        expect(panel).toHaveTextContent("RSI en zona neutra");
        expect(panel).toHaveTextContent("Volumen bajo");
        expect(panel).toHaveTextContent("ema_short");
        expect(panel).toHaveTextContent("63.4");
    });

    it("muestra el bloque IA con modelo, coste y banderas de riesgo", async () => {
        render(<WhyPanel decisionId={7} />);
        await screen.findByTestId("why-panel");

        const ai = screen.getByTestId("why-ai");
        expect(ai).toHaveTextContent("gpt-4o-mini");
        expect(ai).toHaveTextContent("0.0012");
        expect(ai).toHaveTextContent("bajo_volumen");
        expect(ai).toHaveTextContent("BUY");
    });

    it("muestra el bloque de riesgo con la acción real evaluada", async () => {
        render(<WhyPanel decisionId={7} />);
        await screen.findByTestId("why-panel");

        const risk = screen.getByTestId("why-risk");
        expect(risk).toHaveTextContent("ALLOW");
        expect(risk).toHaveTextContent("10");
    });

    it("declara las secciones no disponibles con su motivo exacto", async () => {
        getDecisionWhy.mockResolvedValue(WHY_MINIMAL);

        render(<WhyPanel decisionId={9} />);

        const panel = await screen.findByTestId("why-panel");
        expect(panel).toHaveTextContent(
            "sin correlation_id en el snapshot"
        );
        expect(screen.queryByTestId("why-ai")).toBeNull();
        expect(screen.queryByTestId("why-risk")).toBeNull();
    });

    it("muestra el estado de error sin inventar datos", async () => {
        getDecisionWhy.mockRejectedValue(new Error("offline"));

        render(<WhyPanel decisionId={7} />);
        await flushPromises();

        expect(
            await screen.findByText(
                "No se pudo cargar el Why? de la decisión."
            )
        ).toBeInTheDocument();
    });

    it("pide el detalle de la decisión seleccionada", async () => {
        render(<WhyPanel decisionId={7} />);
        await flushPromises();

        expect(getDecisionWhy).toHaveBeenCalledWith(7);
    });
});
