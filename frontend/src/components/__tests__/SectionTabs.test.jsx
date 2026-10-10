import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SectionTabs from "../SectionTabs";

describe("SectionTabs (RF-6, pestañas reales)", () => {
    afterEach(cleanup);

    it("renderiza las cinco pestañas con roles accesibles", () => {
        render(<SectionTabs value="operar" onChange={() => {}} />);

        const list = screen.getByRole("tablist", {
            name: "Secciones del panel",
        });
        expect(list).toBeInTheDocument();

        const tabs = screen.getAllByRole("tab");
        expect(tabs).toHaveLength(5);
        expect(tabs[0]).toHaveAttribute("aria-selected", "true");
        expect(tabs[0]).toHaveAttribute(
            "aria-controls",
            "panel-operar"
        );
        expect(tabs[1]).toHaveAttribute("tabindex", "-1");
        expect(tabs[2]).toHaveTextContent("Consola");
        expect(tabs[3]).toHaveTextContent("Learning");
        expect(tabs[4]).toHaveTextContent("Historial");
    });

    it("cambia de pestaña con flechas y Home/End", () => {
        const onChange = vi.fn();
        render(<SectionTabs value="operar" onChange={onChange} />);

        const list = screen.getByRole("tablist");

        fireEvent.keyDown(list, { key: "ArrowRight" });
        expect(onChange).toHaveBeenLastCalledWith("estado");

        fireEvent.keyDown(list, { key: "ArrowLeft" });
        expect(onChange).toHaveBeenLastCalledWith("historial");

        fireEvent.keyDown(list, { key: "Home" });
        expect(onChange).toHaveBeenLastCalledWith("operar");

        fireEvent.keyDown(list, { key: "End" });
        expect(onChange).toHaveBeenLastCalledWith("historial");
    });

    it("el clic selecciona la pestaña", () => {
        const onChange = vi.fn();
        render(<SectionTabs value="operar" onChange={onChange} />);

        fireEvent.click(
            screen.getByRole("tab", { name: "Estado" })
        );
        expect(onChange).toHaveBeenCalledWith("estado");
    });
});
