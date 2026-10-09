import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReplayView from "../ReplayView";
import { getDecisionReplay } from "../../api/bot";

vi.mock("../../api/bot", () => ({
    getDecisionWhy: vi.fn(),
    getDecisionReplay: vi.fn(),
    getDecisions: vi.fn(),
}));

const REPLAY_FULL = {
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
    snapshot: {
        price: "100",
        timestamp: "2026-10-07T11:59:00Z",
        indicators: {
            ema_short: "101.5",
            ema_long: "99.25",
            rsi: "63.4",
        },
        candles: [
            { open: "99", close: "100", volume: "12.5" },
        ],
        config: { ema_short_period: 20 },
        correlation_id: "corr-7",
    },
    events: [
        {
            id: 1,
            created_at: "2026-10-07T12:00:01Z",
            level: "INFO",
            service: "decision_store",
            event: "decision.emitted",
            asset: "BTCUSDT",
            correlation_id: "corr-7",
            latency_ms: null,
            result: "ok",
            payload: { decision_id: 7 },
        },
        {
            id: 2,
            created_at: "2026-10-07T12:00:02Z",
            level: "INFO",
            service: "risk_engine",
            event: "risk.evaluated",
            asset: "BTCUSDT",
            correlation_id: "corr-7",
            latency_ms: 12,
            result: "ALLOW",
            payload: { action: "ALLOW" },
        },
        {
            id: 3,
            created_at: "2026-10-07T12:00:03Z",
            level: "INFO",
            service: "bot_loop",
            event: "order.filled",
            asset: "BTCUSDT",
            correlation_id: "corr-7",
            latency_ms: 45,
            result: "ok",
            payload: { decision_id: 7 },
        },
    ],
    ai_evaluation: {
        decision: "BUY",
        direction: "long",
        confidence: "0.72",
        model: "gpt-4o-mini",
        prompt_version: "v3",
        latency_ms: 850,
        cost_usd: "0.0012",
        risk_flags: [],
        created_at: "2026-10-07T12:00:01Z",
    },
    position: {
        symbol: "BTCUSDT",
        quantity: "0.1",
        average_entry_price: "100",
        stop_price: "98",
        take_profit_price: "102",
        status: "CLOSED",
        opened_at: "2026-10-07T12:00:02Z",
        closed_at: "2026-10-07T13:00:00Z",
    },
    outcome: {
        status: "CLOSED",
        pnl_usd: "0.1798",
        filled_at: "2026-10-07T12:00:02Z",
        closed_at: "2026-10-07T13:00:00Z",
    },
    unavailable: [],
};

const REPLAY_NO_CORR = {
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
    snapshot: {
        price: "50",
        timestamp: null,
        indicators: {},
        candles: [],
        config: {},
        correlation_id: null,
    },
    events: [],
    ai_evaluation: null,
    position: null,
    outcome: {
        status: "PENDING",
        pnl_usd: null,
        filled_at: null,
        closed_at: null,
    },
    unavailable: [
        {
            section: "events",
            reason: "sin correlation_id en el snapshot",
        },
        {
            section: "ai",
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

describe("ReplayView (spec 009, RF-5)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getDecisionReplay.mockResolvedValue(REPLAY_FULL);
    });

    afterEach(cleanup);

    it("reconstruye snapshot e histórico de eventos ascendente", async () => {
        render(<ReplayView decisionId={7} />);

        const view = await screen.findByTestId("replay-view");
        expect(view).toHaveTextContent("corr-7");
        expect(view).toHaveTextContent("100");

        const items = screen.getAllByRole("listitem");
        expect(items[0]).toHaveTextContent("Decisión emitida");
        expect(items[1]).toHaveTextContent("Evaluación de riesgo");
        expect(items[2]).toHaveTextContent("Orden ejecutada");
    });

    it("muestra posición, resultado y evaluación IA registradas", async () => {
        render(<ReplayView decisionId={7} />);
        await screen.findByTestId("replay-view");

        const position = screen.getByTestId("replay-position");
        expect(position).toHaveTextContent("BTCUSDT");
        expect(position).toHaveTextContent("0.1");

        const outcome = screen.getByTestId("replay-outcome");
        expect(outcome).toHaveTextContent("CLOSED");
        expect(outcome).toHaveTextContent("0.1798");

        const ai = screen.getByTestId("replay-ai");
        expect(ai).toHaveTextContent("gpt-4o-mini");
        expect(ai).toHaveTextContent("0.0012");
    });

    it("declara eventos e IA no disponibles con su motivo exacto", async () => {
        getDecisionReplay.mockResolvedValue(REPLAY_NO_CORR);

        render(<ReplayView decisionId={9} />);

        const view = await screen.findByTestId("replay-view");
        expect(view).toHaveTextContent(
            "sin correlation_id en el snapshot"
        );
        expect(screen.queryByTestId("replay-ai")).toBeNull();
        expect(screen.queryByTestId("replay-position")).toBeNull();
    });

    it("pide el replay de la decisión seleccionada", async () => {
        render(<ReplayView decisionId={7} />);
        await flushPromises();

        expect(getDecisionReplay).toHaveBeenCalledWith(7);
    });

    it("muestra el estado de error sin inventar datos", async () => {
        getDecisionReplay.mockRejectedValue(new Error("offline"));

        render(<ReplayView decisionId={7} />);
        await flushPromises();

        expect(
            await screen.findByText(
                "No se pudo cargar el replay de la decisión."
            )
        ).toBeInTheDocument();
    });
});
