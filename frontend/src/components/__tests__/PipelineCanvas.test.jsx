import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PipelineCanvas from "../PipelineCanvas";
import { getPipeline } from "../../api/observability";

vi.mock("../../api/observability", () => ({
    getPipeline: vi.fn(),
}));

const NODES = [
    {
        id: "market_data",
        label: "MARKET DATA",
        kind: "source",
        state: "HEALTHY",
        backing: ["binance_klines", "binance_ticker"],
        last_update: "2026-10-07T12:00:00Z",
        reason: "",
        last_event: null,
    },
    {
        id: "risk_engine",
        label: "RISK ENGINE",
        kind: "pipeline",
        state: "ERROR",
        backing: ["risk_engine"],
        last_update: "2026-10-07T12:00:01Z",
        reason: "",
        last_event: {
            service: "risk_engine",
            event: "risk.evaluated",
            result: "BLOCKED",
            latency_ms: 9,
            correlation_id: "corr-1",
            created_at: "2026-10-07T12:00:01Z",
        },
    },
    {
        id: "learning",
        label: "LEARNING",
        kind: "stub",
        state: "DISABLED",
        backing: [],
        last_update: null,
        reason: "pendiente de spec 010",
        last_event: null,
    },
    {
        id: "memory",
        label: "MEMORY",
        kind: "source",
        state: "DISABLED",
        backing: ["database"],
        last_update: null,
        reason: "sin registro de salud",
        last_event: null,
    },
];

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("PipelineCanvas", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getPipeline.mockResolvedValue({ nodes: NODES });
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("renderiza los nodos con su estado y el motivo de los DISABLED", async () => {
        render(<PipelineCanvas />);

        expect(
            await screen.findByTestId("node-market_data")
        ).toBeInTheDocument();
        expect(
            screen.getByTestId("node-market_data")
        ).toHaveTextContent("Saludable");

        expect(
            screen.getByTestId("node-risk_engine")
        ).toHaveTextContent("Error");

        expect(screen.getByTestId("node-learning")).toHaveTextContent(
            "pendiente de spec 010"
        );
        expect(screen.getByTestId("node-memory")).toHaveTextContent(
            "sin registro de salud"
        );
    });

    it("el clic en un nodo abre su payload resumido y notifica al padre", async () => {
        const onSelect = vi.fn();

        render(<PipelineCanvas onSelect={onSelect} />);

        const node = await screen.findByTestId("node-risk_engine");
        fireEvent.click(node);

        expect(onSelect).toHaveBeenCalledWith(
            expect.objectContaining({ id: "risk_engine" })
        );

        const detail = screen.getByTestId("node-detail");
        expect(detail).toHaveTextContent("risk.evaluated");
        expect(detail).toHaveTextContent("corr-1");
        expect(detail).not.toHaveTextContent("binance_klines");
    });

    it("sin nodos muestra un estado vacío honesto", async () => {
        getPipeline.mockResolvedValue({ nodes: [] });

        render(<PipelineCanvas />);
        await flushPromises();

        expect(
            screen.getByText("Sin nodos que mostrar.")
        ).toBeInTheDocument();
    });

    it("refresca el canvas cada 5 segundos", async () => {
        vi.useFakeTimers();

        render(<PipelineCanvas />);
        await flushPromises();

        expect(getPipeline).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(5000);
            await Promise.resolve();
        });

        expect(getPipeline).toHaveBeenCalledTimes(2);
    });
});
