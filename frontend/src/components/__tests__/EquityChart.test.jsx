import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import EquityChart from "../EquityChart";
import { buildEquitySeries } from "../../utils/equity";

afterEach(cleanup);

describe("buildEquitySeries (spec 003, RF-3 / D-2)", () => {
    const trades = [
        {
            id: 2,
            side: "SELL",
            total_usd: "6",
            fee_usd: "0.02",
            realized_pnl_usd: "0.98",
            executed_at: "2026-10-02T10:00:00Z",
        },
        {
            id: 1,
            side: "BUY",
            total_usd: "5",
            fee_usd: "0.01",
            realized_pnl_usd: "0",
            executed_at: "2026-10-01T10:00:00Z",
        },
    ];

    it("ancla la serie en el balance disponible real y la ordena por fecha", () => {
        const series = buildEquitySeries(trades, {
            availableBalance: "10",
            currentTotal: "10.5",
        });

        expect(series).toHaveLength(4);
        expect(series[0].label).toBe("Inicio");
        expect(series[0].value).toBeCloseTo(9.03, 8);
        expect(series[1].value).toBeCloseTo(9.02, 8);
        expect(series[2].value).toBeCloseTo(10, 8);
        expect(series[3].label).toBe("Actual");
        expect(series[3].value).toBeCloseTo(10.5, 8);
    });

    it("sin balance ancla no hay serie (no se inventan datos)", () => {
        expect(buildEquitySeries(trades, {})).toEqual([]);
    });

    it("con una sola referencia devuelve menos de dos puntos", () => {
        const series = buildEquitySeries([], {
            availableBalance: "20",
        });
        expect(series).toHaveLength(1);
    });
});

describe("EquityChart", () => {
    it("muestra el estado de carga", () => {
        render(<EquityChart loading />);

        expect(
            screen.getByTestId("equity-loading")
        ).toHaveTextContent("Cargando curva de equity");
    });

    it("muestra el estado de error", () => {
        render(<EquityChart error="No se pudo cargar." />);

        expect(screen.getByTestId("equity-error")).toHaveTextContent(
            "No se pudo cargar."
        );
    });

    it("muestra el estado vacío sin datos de balance", () => {
        render(<EquityChart />);

        expect(screen.getByTestId("equity-empty")).toHaveTextContent(
            "Sin datos de equity todavía."
        );
    });

    it("renderiza la curva con todos los puntos y el total actual", () => {
        const { container } = render(
            <EquityChart
                availableBalance="10"
                currentTotal="10.5"
                trades={[
                    {
                        id: 1,
                        side: "BUY",
                        total_usd: "5",
                        fee_usd: "0.01",
                        realized_pnl_usd: "0",
                        executed_at: "2026-10-01T10:00:00Z",
                    },
                ]}
            />
        );

        const svg = screen.getByRole("img");
        expect(svg).toHaveAttribute("aria-label");

        const polyline = container.querySelector("polyline");
        expect(polyline).not.toBeNull();
        expect(polyline.getAttribute("points").split(" ")).toHaveLength(3);

        expect(screen.getByText(/Total actual/)).toBeInTheDocument();
        expect(screen.getByText("$10.50")).toBeInTheDocument();
    });

    it("declara la fuente de datos de la serie (D-2)", () => {
        render(
            <EquityChart availableBalance="20" currentTotal="20" />
        );

        expect(screen.getByText(/PnL realizado/)).toBeInTheDocument();
    });
});
