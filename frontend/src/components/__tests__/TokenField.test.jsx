import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import TokenField from "../TokenField";

describe("TokenField", () => {
    beforeEach(() => {
        localStorage.clear();
    });

    afterEach(() => {
        cleanup();
    });

    it("guarda el token introducido en localStorage (RF-8)", () => {
        render(<TokenField />);

        const input = screen.getByPlaceholderText(/token de control/i);
        fireEvent.change(input, { target: { value: "secreto-123" } });
        fireEvent.click(
            screen.getByRole("button", { name: "Guardar" })
        );

        expect(
            localStorage.getItem("crypto_bot_api_token")
        ).toBe("secreto-123");
        expect(
            screen.getByText(/token guardado/i)
        ).toBeInTheDocument();
        expect(screen.getByTestId("token-status")).toBeInTheDocument();
    });

    it("muestra el botón Quitar cuando ya hay token", () => {
        localStorage.setItem("crypto_bot_api_token", "previo");

        render(<TokenField />);

        fireEvent.click(
            screen.getByRole("button", { name: "Quitar" })
        );

        expect(
            localStorage.getItem("crypto_bot_api_token")
        ).toBeNull();
        expect(
            screen.getByText(/token eliminado/i)
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Quitar" })
        ).not.toBeInTheDocument();
    });

    it("no guarda con el campo vacío", () => {
        render(<TokenField />);

        expect(
            screen.getByRole("button", { name: "Guardar" })
        ).toBeDisabled();
    });
});
