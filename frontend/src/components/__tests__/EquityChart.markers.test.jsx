import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EquityChart from "../EquityChart";

afterEach(cleanup);

const TRADES = [
    {
        id: 2,
        side: "SELL",
        symbol: "BTCUSDT",
        total_usd: "6",
        fee_usd: "0.02",
        realized_pnl_usd: "0.98",
        executed_at: "2026-10-02T10:00:00Z",
        decision_id: 8,
    },
    {
        id: 1,
        side: "BUY",
        symbol: "BTCUSDT",
        total_usd: "5",
        fee_usd: "0.01",
        realized_pnl_usd: "0",
        executed_at: "2026-10-01T10:00:00Z",
        decision_id: 7,
    },
    {
        id: 3,
        side: "BUY",
        symbol: "ETHUSDT",
        total_usd: "2",
        fee_usd: "0.01",
        realized_pnl_usd: "0",
        executed_at: "2026-10-03T10:00:00Z",
        decision_id: null,
    },
];

describe("EquityChart marcadores (spec 009, RF-7)", () => {
    it("pinta un marcador por cada operación cerrada enlazada", () => {
        const { container } = render(
            <EquityChart
                trades={TRADES}
                availableBalance="10"
                currentTotal="10.5"
            />
        );

        const markers = container.querySelectorAll(".equity-marker");
        expect(markers).toHaveLength(2);
        expect(markers[0]).toHaveAttribute("data-decision-id", "7");
        expect(markers[1]).toHaveAttribute("data-decision-id", "8");
    });

    it("al seleccionar un marcador notifica la decisión", () => {
        const onSelectDecision = vi.fn();
        const { container } = render(
            <EquityChart
                trades={TRADES}
                availableBalance="10"
                currentTotal="10.5"
                onSelectDecision={onSelectDecision}
            />
        );

        const marker = container.querySelector(
            '.equity-marker[data-decision-id="7"]'
        );
        fireEvent.click(marker);
        expect(onSelectDecision).toHaveBeenCalledWith(7);
    });

    it("las operaciones sin decisión enlazada no generan marcador", () => {
        const { container } = render(
            <EquityChart
                trades={[
                    {
                        id: 3,
                        side: "BUY",
                        symbol: "ETHUSDT",
                        total_usd: "2",
                        fee_usd: "0.01",
                        realized_pnl_usd: "0",
                        executed_at: "2026-10-03T10:00:00Z",
                        decision_id: null,
                    },
                ]}
                availableBalance="10"
                currentTotal="10.5"
            />
        );

        expect(
            container.querySelectorAll(".equity-marker")
        ).toHaveLength(0);
    });

    it("sin operaciones cerradas no hay marcadores", () => {
        const { container } = render(
            <EquityChart
                availableBalance="20"
                currentTotal="20"
            />
        );

        expect(
            container.querySelectorAll(".equity-marker")
        ).toHaveLength(0);
    });
});
