import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Simulation from "../Simulation";
import {
    createAccount,
    getAccounts,
    getBalance,
    getMarketPrices,
    getPositions,
    getSummary,
    getTrades,
} from "../../api/simulation";
import {
    getAiStats,
    getBotMetrics,
    getBotStatus,
    getDecisionReplay,
    getDecisionWhy,
    getDecisions,
} from "../../api/bot";
import {
    getEvents,
    getPipeline,
    getSources,
} from "../../api/observability";

vi.mock("../../api/simulation", () => ({
    createAccount: vi.fn(),
    getAccounts: vi.fn(),
    getBalance: vi.fn(),
    getMarketPrices: vi.fn(),
    getPositions: vi.fn(),
    getSummary: vi.fn(),
    getTrades: vi.fn(),
    createOrder: vi.fn(),
    resetAccount: vi.fn(),
}));

vi.mock("../../api/bot", () => ({
    getBotStatus: vi.fn(),
    getBotMetrics: vi.fn(),
    getDecisions: vi.fn(),
    getAiStats: vi.fn(),
    getDecisionWhy: vi.fn(),
    getDecisionReplay: vi.fn(),
    startBot: vi.fn(),
    stopBot: vi.fn(),
}));

vi.mock("../../api/observability", () => ({
    getPipeline: vi.fn(),
    getEvents: vi.fn(),
    getSources: vi.fn(),
}));

vi.mock("../../api/learning", () => ({
    getHypotheses: vi.fn(),
    getKnowledge: vi.fn(),
    createHypothesis: vi.fn(),
    transitionHypothesis: vi.fn(),
    evaluateHypothesis: vi.fn(),
    getStrategyVersions: vi.fn(),
}));

const SUMMARY = {
    balance: {
        available_usd: "20.00",
        invested_usd: "0.00",
        market_value_usd: "0.00",
        realized_pnl_usd: "0E-8",
        unrealized_pnl_usd: "0E-8",
        total_balance_usd: "20.00",
    },
};

describe("Simulation (NFR accesibilidad, T6)", () => {
    beforeEach(() => {
        vi.clearAllMocks();

        getAccounts.mockResolvedValue([
            { id: 1, name: "Default Simulation", created_at: "2026-10-01T00:00:00Z" },
        ]);
        createAccount.mockResolvedValue({});
        getSummary.mockResolvedValue(SUMMARY);
        getBalance.mockResolvedValue(null);
        getPositions.mockResolvedValue([]);
        getTrades.mockResolvedValue([]);
        getMarketPrices.mockResolvedValue([]);

        getBotStatus.mockResolvedValue({
            fase: "SIMULATION",
            running: false,
            breaker_active: false,
            consecutive_failures: 0,
            breaker_reason: null,
            live_blockers: [],
        });
        getBotMetrics.mockResolvedValue({
            balance_usd: "20.00",
            open_positions: 0,
            realized_pnl_usd: "0E-8",
            unrealized_pnl_usd: "0E-8",
            drawdown_pct: "0.00",
            opens_today: 0,
            daily_loss_usd: "0.00",
        });
        getDecisions.mockResolvedValue({ decisiones: [] });
        getAiStats.mockResolvedValue({
            queries_24h: 0,
            cost_usd_24h: "0",
            avg_latency_ms: null,
            by_status: {},
            by_decision: {},
            generated_at: "2026-10-07T12:00:00Z",
        });
        getDecisionWhy.mockResolvedValue({
            decision: { id: 7 },
            factors: { positive: [], negative: [], indicators: {} },
            ai: null,
            risk: null,
            outcome: { status: "PENDING", pnl_usd: null },
            unavailable: [],
        });
        getDecisionReplay.mockResolvedValue({
            decision: { id: 7 },
            snapshot: {
                price: null,
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
            unavailable: [],
        });
        getSources.mockResolvedValue({ sources: [] });
        getPipeline.mockResolvedValue({ nodes: [] });
        getEvents.mockResolvedValue({ events: [] });
    });

    afterEach(cleanup);

    it("marca los iconos decorativos de estados vacíos como aria-hidden", async () => {
        const { container } = render(<Simulation />);

        await screen.findByText("Todavía no hay operaciones.");

        const icons = container.querySelectorAll(".empty-state-icon");
        expect(icons.length).toBeGreaterThanOrEqual(3);
        for (const icon of icons) {
            expect(icon).toHaveAttribute("aria-hidden", "true");
        }
    });

    it("sin exponenciales en la página (RF-5/T5)", async () => {
        const { container } = render(<Simulation />);

        await screen.findByText("Todavía no hay operaciones.");

        expect(container.textContent).not.toMatch(/0E-/);
    });

    it("shell de tres columnas: rail, workspace y sidebar (RF-6)", async () => {
        render(<Simulation />);

        await screen.findByText("Todavía no hay operaciones.");

        expect(
            screen.getByRole("navigation", {
                name: "Secciones del panel",
            })
        ).toBeInTheDocument();
        expect(screen.getByRole("main")).toBeInTheDocument();
        expect(
            screen.getByRole("complementary", {
                name: "Panel lateral",
            })
        ).toBeInTheDocument();
        expect(
            screen.getByRole("tablist", {
                name: "Secciones del panel",
            })
        ).toBeInTheDocument();
    });

    it("las pestañas alternan el panel visible (RF-6)", async () => {
        render(<Simulation />);

        await screen.findByText("Todavía no hay operaciones.");

        fireEvent.click(
            screen.getByRole("tab", { name: "Estado" })
        );

        const metrics = await screen.findByTestId("metrics-panel");
        expect(metrics).toBeVisible();

        const operar = document.getElementById("panel-operar");
        expect(operar).not.toBeVisible();
    });

    it("la pestaña Consola monta el canvas y el recorrido (spec 009)", async () => {
        render(<Simulation />);

        await screen.findByText("Todavía no hay operaciones.");

        fireEvent.click(
            screen.getByRole("tab", { name: "Consola" })
        );

        expect(
            await screen.findByTestId("pipeline-canvas")
        ).toBeVisible();
        expect(
            screen.getByTestId("event-stream")
        ).toBeVisible();
        expect(
            screen.getByTestId("header-panel")
        ).toBeVisible();
        expect(
            screen.getByTestId("decision-inspector")
        ).toBeVisible();
    });

    it("el marcador de equity abre el inspector de su decisión (RF-7)", async () => {
        getDecisions.mockResolvedValue({
            decisiones: [
                {
                    id: 7,
                    symbol: "BTCUSDT",
                    side: "BUY",
                    status: "CLOSED",
                    pnl_usd: "0.1798",
                    created_at: "2026-10-07T12:00:00Z",
                },
            ],
        });
        getTrades.mockResolvedValue([
            {
                id: 1,
                side: "BUY",
                symbol: "BTCUSDT",
                quantity: "0.1",
                price: "100",
                total_usd: "10",
                fee_usd: "0.01",
                realized_pnl_usd: "0",
                executed_at: "2026-10-01T10:00:00Z",
                decision_id: 7,
            },
            {
                id: 2,
                side: "SELL",
                symbol: "BTCUSDT",
                quantity: "0.1",
                price: "104",
                total_usd: "10.4",
                fee_usd: "0.01",
                realized_pnl_usd: "0.39",
                executed_at: "2026-10-02T10:00:00Z",
                decision_id: 7,
            },
        ]);

        const { container } = render(<Simulation />);

        await screen.findByText("Historial de operaciones");

        const marker = container.querySelector(
            '.equity-marker[data-decision-id="7"]'
        );
        fireEvent.click(marker);

        expect(
            await screen.findByTestId("decision-inspector")
        ).toBeVisible();
        expect(getDecisionWhy).toHaveBeenCalledWith(7);
        expect(
            screen.getByTestId("decision-timeline-7")
        ).toBeVisible();
    });
});
