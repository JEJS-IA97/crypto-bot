import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import LivePrices from "../LivePrices";

afterEach(cleanup);

const PRICES = [
    { symbol: "BTCUSDT", price_usd: "82500.00" },
    { symbol: "ETHUSDT", price_usd: "3000.00" },
];

describe("LivePrices", () => {
    it("marca la subida con flecha verde y %", () => {
        render(
            <LivePrices
                prices={[PRICES[0]]}
                priceHistory={{ BTCUSDT: [82000, 82500] }}
            />
        );

        const row = screen.getByText("BTC").closest(".price-row");

        expect(row.querySelector(".price-value")).toHaveClass(
            "value-positive"
        );
        expect(row.textContent).toContain("▲");
        expect(row.textContent).toContain("0.61%");
        expect(
            row.querySelector(".price-spark-up")
        ).toBeTruthy();
    });

    it("marca la bajada con flecha roja y %", () => {
        render(
            <LivePrices
                prices={[PRICES[0]]}
                priceHistory={{ BTCUSDT: [83000, 82500] }}
            />
        );

        const row = screen.getByText("BTC").closest(".price-row");

        expect(row.querySelector(".price-value")).toHaveClass(
            "value-negative"
        );
        expect(row.textContent).toContain("▼");
        expect(row.textContent).toContain("0.60%");
        expect(
            row.querySelector(".price-spark-down")
        ).toBeTruthy();
    });

    it("sin historial no muestra delta", () => {
        render(<LivePrices prices={PRICES} priceHistory={{}} />);

        const row = screen.getByText("BTC").closest(".price-row");

        expect(row.querySelector(".price-delta")).toBeNull();
        expect(row.textContent).toContain("$82,500.00");
    });
});
