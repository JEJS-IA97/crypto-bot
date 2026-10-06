import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MetricsPanel from "../MetricsPanel";
import {
    getBotMetrics,
    getBotStatus,
    getDecisions,
} from "../../api/bot";

vi.mock("../../api/bot", () => ({
    getBotStatus: vi.fn(),
    getBotMetrics: vi.fn(),
    getDecisions: vi.fn(),
}));

const STATUS_STOPPED = {
    fase: "SIMULATION",
    running: false,
    breaker_active: false,
    consecutive_failures: 0,
    breaker_reason: null,
    live_blockers: [],
};

const METRICS = {
    generated_at: "2026-10-05T12:00:00",
    available_usd: "19.00",
    market_value_usd: "1.00",
    balance_usd: "20.00",
    open_positions: 1,
    realized_pnl_usd: "0.50",
    unrealized_pnl_usd: "-0.10",
    drawdown_pct: "1.20",
    opens_today: 2,
    daily_loss_usd: "0.00",
    daily_blocked: false,
    block_reason: null,
};

const DECISIONS = [
    {
        id: 1,
        symbol: "BTCUSDT",
        side: "BUY",
        origin: "TECHNICAL",
        status: "CLOSED",
        rejection_reason: null,
        pnl_usd: "0.10",
        snapshot: { rsi: 30 },
    },
];

const REJECTED = [
    {
        id: 2,
        symbol: "ETHUSDT",
        side: "BUY",
        origin: "EXTERNAL",
        status: "REJECTED",
        rejection_reason: "signal_expired",
        pnl_usd: null,
        snapshot: { price: "100" },
    },
];

function mockPayloads(
    status = STATUS_STOPPED,
    metrics = METRICS,
    decisions = DECISIONS,
    rejected = REJECTED,
) {
    getBotStatus.mockResolvedValue(status);
    getBotMetrics.mockResolvedValue(metrics);
    getDecisions.mockImplementation((params = {}) =>
        Promise.resolve({
            decisiones:
                params.status === "REJECTED" ? rejected : decisions,
        })
    );
}

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("MetricsPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("muestra estado, métricas, historial y rechazos con motivo", async () => {
        mockPayloads();

        render(<MetricsPanel />);

        const state = await screen.findByTestId("bot-state");
        expect(state).toHaveTextContent("Detenido");

        expect(screen.getByTestId("bot-phase")).toHaveTextContent(
            "SIMULATION"
        );

        // RF-17: saldo, posiciones, PnL, drawdown, aperturas y pérdida.
        expect(
            screen.getByTestId("metric-balance")
        ).toHaveTextContent("20.00 USD");
        expect(screen.getByText("Posiciones abiertas")).toBeInTheDocument();
        expect(screen.getByText("PnL realizado")).toBeInTheDocument();
        expect(screen.getByText("PnL no realizado")).toBeInTheDocument();
        expect(screen.getByText("Drawdown")).toBeInTheDocument();
        expect(screen.getByText("Aperturas del día")).toBeInTheDocument();
        expect(screen.getByText("Pérdida del día")).toBeInTheDocument();

        // Historial con la señal asociada (snapshot) y su resultado.
        const snapshot = await screen.findByTestId("decision-1");
        expect(snapshot).toHaveTextContent('"rsi": 30');
        expect(screen.getByText("CLOSED")).toBeInTheDocument();
        expect(screen.getByText("0.10 USD")).toBeInTheDocument();

        // Señales rechazadas con su motivo (RF-18).
        const rejectedList = await screen.findByTestId(
            "rejected-signals"
        );
        expect(rejectedList).toHaveTextContent("ETHUSDT");
        expect(rejectedList).toHaveTextContent("signal_expired");
    });

    it("muestra 'Bloqueado' con el motivo del breaker", async () => {
        mockPayloads({
            ...STATUS_STOPPED,
            breaker_active: true,
            breaker_reason: "5 fallos consecutivos",
        });

        render(<MetricsPanel />);

        const state = await screen.findByTestId("bot-state");
        expect(state).toHaveTextContent("Bloqueado");

        const reason = await screen.findByTestId("block-reason");
        expect(reason).toHaveTextContent("5 fallos consecutivos");
    });

    it("refresca los datos cada 5 segundos", async () => {
        vi.useFakeTimers();
        mockPayloads();

        render(<MetricsPanel />);
        await flushPromises();

        expect(getBotStatus).toHaveBeenCalledTimes(1);
        expect(getBotMetrics).toHaveBeenCalledTimes(1);
        expect(getDecisions).toHaveBeenCalledTimes(2);

        await act(async () => {
            vi.advanceTimersByTime(5000);
            await Promise.resolve();
        });

        expect(getBotStatus).toHaveBeenCalledTimes(2);
        expect(getBotMetrics).toHaveBeenCalledTimes(2);
        expect(getDecisions).toHaveBeenCalledTimes(4);
    });
});
