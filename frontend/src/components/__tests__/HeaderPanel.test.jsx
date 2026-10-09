import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HeaderPanel from "../HeaderPanel";
import {
    getAiStats,
    getBotMetrics,
    getBotStatus,
    getDecisions,
} from "../../api/bot";
import { getSources } from "../../api/observability";

vi.mock("../../api/bot", () => ({
    getBotStatus: vi.fn(),
    getBotMetrics: vi.fn(),
    getDecisions: vi.fn(),
    getAiStats: vi.fn(),
}));

vi.mock("../../api/observability", () => ({
    getSources: vi.fn(),
}));

const STATUS_RUNNING = {
    fase: "SIMULATION",
    running: true,
    breaker_active: false,
    consecutive_failures: 0,
    breaker_reason: null,
    live_blockers: [],
};

const METRICS = {
    generated_at: "2026-10-07T12:00:00Z",
    available_usd: "19.50",
    market_value_usd: "0.50",
    balance_usd: "20.00",
    open_positions: 1,
    realized_pnl_usd: "0.40",
    unrealized_pnl_usd: "0.10",
    drawdown_pct: "1.20",
    opens_today: 2,
    daily_realized_pnl_usd: "0.30",
    daily_loss_usd: "0.00",
    daily_blocked: false,
    block_reason: null,
};

const AI_STATS = {
    queries_24h: 12,
    cost_usd_24h: "0.0021",
    avg_latency_ms: 321,
    by_status: { OK: 12 },
    by_decision: { BUY: 2 },
    generated_at: "2026-10-07T12:00:00Z",
};

const SOURCES = {
    sources: [
        { name: "binance_klines", state: "HEALTHY" },
        { name: "database", state: "ERROR" },
        { name: "news_rss", state: "DISABLED" },
    ],
};

const CLOSED = {
    decisiones: [{ id: 1 }, { id: 2 }, { id: 3 }],
};

function mockPayloads({
    status = STATUS_RUNNING,
    metrics = METRICS,
    aiStats = AI_STATS,
    sources = SOURCES,
    closed = CLOSED,
} = {}) {
    getBotStatus.mockResolvedValue(status);
    getBotMetrics.mockResolvedValue(metrics);
    getAiStats.mockResolvedValue(aiStats);
    getSources.mockResolvedValue(sources);
    getDecisions.mockResolvedValue(closed);
}

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("HeaderPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("muestra estado real, capital, PnL, IA y salud de fuentes", async () => {
        mockPayloads();

        render(<HeaderPanel />);

        expect(await screen.findByTestId("header-state")).toHaveTextContent(
            "OPERANDO"
        );
        expect(screen.getByTestId("header-phase")).toHaveTextContent(
            "SIMULATION"
        );
        expect(screen.getByTestId("header-clock")).toHaveTextContent(/UTC/);

        expect(screen.getByTestId("header-capital")).toHaveTextContent(
            "20.00 USD"
        );
        expect(screen.getByTestId("header-pnl-daily")).toHaveTextContent(
            "0.30 USD"
        );
        expect(screen.getByTestId("header-pnl-total")).toHaveTextContent(
            "0.50 USD"
        );
        expect(screen.getByTestId("header-drawdown")).toHaveTextContent(
            "1.20%"
        );
        expect(screen.getByTestId("header-open")).toHaveTextContent("1");
        expect(screen.getByTestId("header-closed")).toHaveTextContent("3");

        expect(screen.getByTestId("header-ai-queries")).toHaveTextContent(
            "12"
        );
        expect(screen.getByTestId("header-ai-cost")).toHaveTextContent(
            "0.0021 USD"
        );
        expect(screen.getByTestId("header-ai-latency")).toHaveTextContent(
            "321 ms"
        );
        expect(screen.getByTestId("header-sources")).toHaveTextContent(
            "HEALTHY 1"
        );
        expect(screen.getByTestId("header-updated")).toHaveTextContent(
            "2026-10-07"
        );
    });

    it("mapea el breaker a EMERGENCIA (estados reales, D-5)", async () => {
        mockPayloads({
            status: {
                ...STATUS_RUNNING,
                running: false,
                breaker_active: true,
                breaker_reason: "5 fallos consecutivos",
            },
        });

        render(<HeaderPanel />);

        expect(await screen.findByTestId("header-state")).toHaveTextContent(
            "EMERGENCIA"
        );
        expect(screen.getByTestId("header-detail")).toHaveTextContent(
            "5 fallos consecutivos"
        );
    });

    it("si las stats de IA fallan, el resto del header sigue vivo", async () => {
        mockPayloads();
        getAiStats.mockRejectedValue(new Error("backend caído"));

        render(<HeaderPanel />);

        expect(await screen.findByTestId("header-capital")).toHaveTextContent(
            "20.00 USD"
        );
        expect(screen.getByTestId("header-ai-queries")).toHaveTextContent(
            "sin datos"
        );
        expect(screen.queryByText(/No se pudo cargar/)).not.toBeInTheDocument();
    });

    it("refresca los datos cada 5 segundos", async () => {
        vi.useFakeTimers();
        mockPayloads();

        render(<HeaderPanel />);
        await flushPromises();

        expect(getBotStatus).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(5000);
            await Promise.resolve();
        });

        expect(getBotStatus).toHaveBeenCalledTimes(2);
    });
});
