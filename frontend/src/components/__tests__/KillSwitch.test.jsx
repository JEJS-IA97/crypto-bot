import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import KillSwitch from "../KillSwitch";
import { getBotStatus, startBot, stopBot } from "../../api/bot";

vi.mock("../../api/bot", () => ({
    getBotStatus: vi.fn(),
    startBot: vi.fn(),
    stopBot: vi.fn(),
}));

const STATUS_RUNNING = {
    fase: "SIMULATION",
    running: true,
    breaker_active: false,
    consecutive_failures: 0,
    breaker_reason: null,
    live_blockers: [],
};

describe("KillSwitch", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
    });

    it("detiene el bot y refleja el estado detenido (RF-3)", async () => {
        getBotStatus.mockResolvedValue(STATUS_RUNNING);
        stopBot.mockResolvedValue({
            running: false,
            mensaje: "Bot detenido; no saldrán órdenes nuevas.",
        });

        render(<KillSwitch />);

        const button = await screen.findByRole("button", {
            name: "Detener",
        });
        expect(screen.getByTestId("kill-state")).toHaveTextContent(
            "Activo"
        );

        fireEvent.click(button);

        await waitFor(() => expect(stopBot).toHaveBeenCalledTimes(1));
        expect(
            await screen.findByRole("button", { name: "Arrancar" })
        ).toBeInTheDocument();
        expect(screen.getByTestId("kill-state")).toHaveTextContent(
            "Detenido"
        );
    });

    it("arranca el bot cuando está detenido (RF-19)", async () => {
        getBotStatus.mockResolvedValue({
            ...STATUS_RUNNING,
            running: false,
        });
        startBot.mockResolvedValue({
            running: true,
            mensaje: "Bot arrancado.",
        });

        render(<KillSwitch />);

        fireEvent.click(
            await screen.findByRole("button", { name: "Arrancar" })
        );

        await waitFor(() => expect(startBot).toHaveBeenCalledTimes(1));
        expect(
            await screen.findByRole("button", { name: "Detener" })
        ).toBeInTheDocument();
        expect(screen.getByTestId("kill-state")).toHaveTextContent(
            "Activo"
        );
    });

    it("muestra el motivo del backend si la API lo rechaza", async () => {
        getBotStatus.mockResolvedValue({
            ...STATUS_RUNNING,
            running: false,
        });
        startBot.mockRejectedValue({
            response: { data: { detail: "Token requerido." } },
        });

        render(<KillSwitch />);

        fireEvent.click(
            await screen.findByRole("button", { name: "Arrancar" })
        );

        expect(await screen.findByText("Token requerido.")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Arrancar" })
        ).toBeInTheDocument();
        expect(screen.getByTestId("kill-state")).toHaveTextContent(
            "Detenido"
        );
    });
});
