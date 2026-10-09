import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EventStream from "../EventStream";
import { getEvents } from "../../api/observability";

vi.mock("../../api/observability", () => ({
    getEvents: vi.fn(),
}));

const EVENTS = [
    {
        id: 3,
        created_at: "2026-10-07T12:00:03Z",
        level: "INFO",
        service: "bot_loop",
        event: "order.filled",
        asset: "BTCUSDT",
        correlation_id: "corr-a",
        mode: "paper",
        latency_ms: 45,
        result: "ok",
        payload: { decision_id: 7 },
    },
    {
        id: 1,
        created_at: "2026-10-07T12:00:01Z",
        level: "INFO",
        service: "decision_store",
        event: "decision.emitted",
        asset: "BTCUSDT",
        correlation_id: "corr-a",
        mode: "paper",
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
        correlation_id: "corr-a",
        mode: "paper",
        latency_ms: 12,
        result: "ALLOW",
        payload: { action: "ALLOW" },
    },
    {
        id: 4,
        created_at: "2026-10-07T13:00:00Z",
        level: "INFO",
        service: "bot_loop",
        event: "cycle.completed",
        asset: null,
        correlation_id: null,
        mode: "paper",
        latency_ms: 200,
        result: "ok",
        payload: {},
    },
];

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("EventStream", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getEvents.mockResolvedValue({ events: EVENTS });
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("muestra la secuencia real de la correlation con timestamps y latencias", async () => {
        render(<EventStream correlationId="corr-a" />);

        const flow = await screen.findByTestId("flow-corr-a");
        expect(flow).toHaveTextContent("Decisión emitida");
        expect(flow).toHaveTextContent("Evaluación de riesgo");
        expect(flow).toHaveTextContent("Orden ejecutada");

        expect(flow).toHaveTextContent("2026-10-07T12:00:01Z");
        expect(flow).toHaveTextContent("12 ms");
        expect(flow).toHaveTextContent("ALLOW");

        // Etapas del brief SOLO cuando existe el evento (sin humo, §35).
        expect(screen.queryByText("Consulta IA")).not.toBeInTheDocument();
    });

    it("pide los eventos filtrados por correlation_id al backend", async () => {
        render(<EventStream correlationId="corr-a" />);
        await flushPromises();

        expect(getEvents).toHaveBeenCalledWith({
            correlation_id: "corr-a",
            limit: 50,
        });
    });

    it("sin eventos muestra 'sin actividad registrada' (nunca anima)", async () => {
        getEvents.mockResolvedValue({ events: [] });

        render(<EventStream correlationId="corr-vacio" />);
        await flushPromises();

        expect(
            screen.getByText("Sin actividad registrada.")
        ).toBeInTheDocument();
    });

    it("incluye un resumen del payload real del evento", async () => {
        render(<EventStream correlationId="corr-a" />);

        const flow = await screen.findByTestId("flow-corr-a");
        expect(flow).toHaveTextContent('"action": "ALLOW"');
    });
});
