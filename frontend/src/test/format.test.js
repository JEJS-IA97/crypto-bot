import { describe, expect, it } from "vitest";

import { formatDateTime, formatMoney } from "../utils/format";

describe("formatMoney (spec 003, RF-5)", () => {
    it("sin notación exponencial: 0E-8 se muestra como 0.00", () => {
        expect(formatMoney("0E-8")).toBe("0.00");
        expect(formatMoney(0)).toBe("0.00");
        expect(formatMoney("0")).toBe("0.00");
    });

    it("mínimo 2 decimales y precisión máxima de 8", () => {
        expect(formatMoney("19.89734056")).toBe("19.89734056");
        expect(formatMoney("-0.1")).toBe("-0.10");
        expect(formatMoney("0.5")).toBe("0.50");
    });

    it("agrupa valores grandes de forma localizada", () => {
        expect(formatMoney("1234567.5")).toBe("1,234,567.50");
    });

    it("valores ausentes o inválidos caen a 0.00", () => {
        expect(formatMoney(undefined)).toBe("0.00");
        expect(formatMoney(null)).toBe("0.00");
        expect(formatMoney("abc")).toBe("0.00");
    });
});

describe("formatDateTime (spec 003, RF-5)", () => {
    it("formatea fechas con locale explícito", () => {
        expect(formatDateTime("2026-10-01T10:00:00Z")).toMatch(/2026/);
    });

    it("fechas inválidas devuelven rayo", () => {
        expect(formatDateTime("no-date")).toBe("—");
    });
});
