import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TradingPanel from "../TradingPanel";
import { createOrder } from "../../api/simulation";

vi.mock("../../api/simulation", () => ({
    createOrder: vi.fn(),
}));

const MARKET_PRICES = [
    { symbol: "BTCUSDT", price_usd: "50000" },
    { symbol: "ETHUSDT", price_usd: "2000" },
];

function renderPanel(overrides = {}) {
    return render(
        <TradingPanel
            accountId={1}
            marketPrices={MARKET_PRICES}
            positions={[]}
            availableBalance="600"
            onOrderExecuted={overrides.onOrderExecuted ?? vi.fn()}
            {...overrides}
        />
    );
}

describe("TradingPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(cleanup);

    it("prefill del precio límite con el precio de mercado", () => {
        renderPanel();

        expect(
            screen.getByLabelText("Precio límite (USD)")
        ).toHaveValue(50000);
    });

    it("actualiza el precio límite al cambiar de activo", () => {
        renderPanel();

        fireEvent.change(screen.getByLabelText("Activo"), {
            target: { value: "ETHUSDT" },
        });

        expect(
            screen.getByLabelText("Precio límite (USD)")
        ).toHaveValue(2000);
    });

    it("ejecuta la orden y recarga los datos (T7)", async () => {
        createOrder.mockResolvedValue({ id: 1 });
        const onOrderExecuted = vi.fn().mockResolvedValue(undefined);

        renderPanel({ onOrderExecuted });

        fireEvent.change(screen.getByLabelText("Cantidad"), {
            target: { value: "0.0001" },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "Ejecutar compra" })
        );

        await waitFor(() =>
            expect(createOrder).toHaveBeenCalledTimes(1)
        );
        expect(createOrder).toHaveBeenCalledWith(
            1,
            expect.objectContaining({
                symbol: "BTCUSDT",
                side: "BUY",
            })
        );
        expect(onOrderExecuted).toHaveBeenCalledTimes(1);
        expect(
            screen.getByText("Compra ejecutada correctamente.")
        ).toBeInTheDocument();
    });
});
