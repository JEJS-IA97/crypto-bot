import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PriceChart from "../PriceChart";

afterEach(cleanup);

describe("PriceChart", () => {
    it("dibuja la curva con historial de ticks", () => {
        render(
            <PriceChart
                points={[100, 105, 110]}
                symbol="BTCUSDT"
            />
        );

        expect(
            screen.getByTestId("price-chart")
        ).toBeTruthy();
        expect(
            screen.getByRole("img").getAttribute("aria-label")
        ).toBe("Gráfica de precio de BTCUSDT");
        expect(
            screen.getByTestId("price-chart").textContent
        ).toContain("10.00%");
    });

    it("sin historial muestra el estado vacío", () => {
        render(<PriceChart points={[]} />);

        expect(
            screen.getByTestId("price-chart-empty")
        ).toBeTruthy();
    });
});
