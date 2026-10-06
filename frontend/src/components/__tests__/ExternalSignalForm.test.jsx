import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ExternalSignalForm from "../ExternalSignalForm";
import { sendExternalSignal } from "../../api/signals";

vi.mock("../../api/signals", () => ({
    sendExternalSignal: vi.fn(),
}));

describe("ExternalSignalForm", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(cleanup);

    it("envía la señal y muestra el resultado aceptado", async () => {
        sendExternalSignal.mockResolvedValue({
            estado: "aceptada",
            symbol: "BTCUSDT",
            side: "BUY",
            quantity: "0.02040",
            source: "panel",
        });

        render(<ExternalSignalForm />);

        fireEvent.change(screen.getByLabelText("Par"), {
            target: { value: "ETHUSDT" },
        });
        fireEvent.change(screen.getByLabelText("Lado"), {
            target: { value: "SELL" },
        });
        fireEvent.change(screen.getByLabelText("Precio límite"), {
            target: { value: "2500.5" },
        });
        fireEvent.change(screen.getByLabelText("Cantidad"), {
            target: { value: "1.5" },
        });
        fireEvent.change(screen.getByLabelText("Fuente"), {
            target: { value: "copy" },
        });

        fireEvent.click(
            screen.getByRole("button", { name: "Enviar señal" })
        );

        await waitFor(() =>
            expect(sendExternalSignal).toHaveBeenCalledTimes(1)
        );
        expect(sendExternalSignal).toHaveBeenCalledWith({
            symbol: "ETHUSDT",
            side: "SELL",
            price_limit: "2500.5",
            quantity: "1.5",
            source: "copy",
        });

        const result = await screen.findByTestId("signal-result");
        expect(result).toHaveTextContent("Aceptada");
        expect(result).toHaveTextContent("0.02040");
    });

    it("muestra la señal rechazada con su motivo (RF-8)", async () => {
        sendExternalSignal.mockResolvedValue({
            estado: "rechazada",
            motivo: "signal_expired",
            symbol: "BTCUSDT",
            side: "BUY",
        });

        render(<ExternalSignalForm />);

        fireEvent.click(
            screen.getByRole("button", { name: "Enviar señal" })
        );

        const result = await screen.findByTestId("signal-result");
        expect(result).toHaveTextContent("Rechazada");
        expect(result).toHaveTextContent("signal_expired");
    });

    it("valida el precio en cliente sin llamar a la API", async () => {
        render(<ExternalSignalForm />);

        fireEvent.change(screen.getByLabelText("Precio límite"), {
            target: { value: "-1" },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "Enviar señal" })
        );

        expect(
            await screen.findByText("El precio debe ser mayor que cero.")
        ).toBeInTheDocument();
        expect(sendExternalSignal).not.toHaveBeenCalled();
    });
});
