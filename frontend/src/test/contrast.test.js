import { describe, expect, it } from "vitest";

import { loadCss } from "./css";

const css = loadCss();

function token(name) {
    const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
    if (!match) {
        throw new Error(`token --${name} no encontrado`);
    }
    return match[1].trim();
}

function toRgb(hex) {
    const clean = hex.replace("#", "");
    const full =
        clean.length === 3
            ? clean
                  .split("")
                  .map((char) => char + char)
                  .join("")
            : clean;

    return [0, 2, 4].map((index) =>
        parseInt(full.slice(index, index + 2), 16)
    );
}

function luminance(hex) {
    const [r, g, b] = toRgb(hex).map((value) => {
        const channel = value / 255;
        return channel <= 0.03928
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4;
    });

    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
    const la = luminance(a);
    const lb = luminance(b);
    const [light, dark] = la > lb ? [la, lb] : [lb, la];
    return (light + 0.05) / (dark + 0.05);
}

describe("contraste WCAG AA (paleta design.json, RF-6)", () => {
    it("texto secundario sobre fondo principal", () => {
        expect(
            contrast(token("text-secondary"), token("bg-main"))
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("acento sobre el rail negro (icono activo)", () => {
        expect(
            contrast(token("accent"), token("bg-rail"))
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("botón primario: tinta oscura sobre turquesa", () => {
        expect(
            contrast(token("accent-ink"), token("color-buy"))
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("acciones blancas: tinta oscura sobre blanco", () => {
        expect(
            contrast(
                token("white-button-ink"),
                token("white-button")
            )
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("destructiva: texto rojo sobre fondo principal", () => {
        expect(
            contrast(token("color-sell"), token("bg-main"))
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("tab Vender: tinta oscura sobre rojo", () => {
        expect(
            contrast(token("negative-ink"), token("color-sell"))
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("PnL positivo y negativo sobre superficie de tarjeta", () => {
        expect(
            contrast(token("positive"), token("surface-soft"))
        ).toBeGreaterThanOrEqual(4.5);
        expect(
            contrast(token("negative"), token("surface-soft"))
        ).toBeGreaterThanOrEqual(4.5);
    });

    it("valores sobre superficie de panel", () => {
        expect(
            contrast(token("text-value"), token("surface"))
        ).toBeGreaterThanOrEqual(4.5);
        expect(
            contrast(token("text-secondary"), token("surface"))
        ).toBeGreaterThanOrEqual(4.5);
    });
});
