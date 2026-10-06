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
import { getBotMetrics, getBotStatus, getDecisions } from "../../api/bot";

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
    startBot: vi.fn(),
    stopBot: vi.fn(),
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
});
