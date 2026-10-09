import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Timeline from "../Timeline";
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
        indicators: { rsi: "63.4" },
        candles: [],
        config: {},
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
            payload: {},
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
    ai_evaluation: null,
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
    unavailable: [
        {
            section: "ai",
            reason: "sin evaluación IA para esta decisión",
        },
    ],
};

const REPLAY_NO_EVENTS = {
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
    ],
};

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("Timeline (spec 009, RF-6)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getDecisionReplay.mockResolvedValue(REPLAY_FULL);
    });

    afterEach(cleanup);

    it("ordena decisión, eventos, fills y cierre con su PnL", async () => {
        render(<Timeline decisionId={7} />);

        const list = await screen.findByTestId(
            "decision-timeline-7"
        );
        const items = screen.getAllByRole("listitem");
        expect(items[0]).toHaveTextContent("Decisión creada");
        expect(items[0]).toHaveTextContent("2026-10-07T12:00:00Z");
        expect(items[1]).toHaveTextContent("Decisión emitida");
        expect(items[2]).toHaveTextContent("Orden ejecutada");
        expect(list).toHaveTextContent(
            "Posición cerrada · PnL 0.1798"
        );
    });

    it("sin eventos disponibles lo declara con el motivo", async () => {
        getDecisionReplay.mockResolvedValue(REPLAY_NO_EVENTS);

        render(<Timeline decisionId={9} />);

        const list = await screen.findByTestId(
            "decision-timeline-9"
        );
        expect(list).toHaveTextContent(
            "sin correlation_id en el snapshot"
        );
    });

    it("pide el replay de la decisión seleccionada", async () => {
        render(<Timeline decisionId={7} />);
        await flushPromises();

        expect(getDecisionReplay).toHaveBeenCalledWith(7);
    });
});
