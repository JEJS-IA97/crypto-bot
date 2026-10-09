import { describe, expect, it } from "vitest";

import { loadCss, loadCssFiles } from "./css";

const css = loadCss();
const root = css.slice(
    0,
    css.indexOf("{", css.indexOf(":root")) + 2500
);

describe("design system (spec 003 RF-6, design.json)", () => {
    it("define la paleta de design.json en :root", () => {
        for (const declaration of [
            "--bg-main: #1d1e21",
            "--bg-rail: #050505",
            "--surface: #202124",
            "--divider: #303236",
            "--accent: #27e7cf",
            "--color-buy: #27e7cf",
            "--negative: #ff4d5a",
        ]) {
            expect(root).toContain(declaration);
        }
    });

    it("define escalas de espaciado, radio y tipografía", () => {
        for (const declaration of [
            "--space-4: 16px",
            "--space-8: 32px",
            "--radius-md: 10px",
            "--radius-xl: 16px",
            "--font-size-page-title",
            "--font-sans",
        ]) {
            expect(root).toContain(declaration);
        }
    });

    it("usa la escala de espaciado en layout y componentes", () => {
        const uses = css.match(/var\(--space-\d+\)/g) ?? [];
        expect(uses.length).toBeGreaterThan(15);
    });

    it("shell de tres columnas full-bleed (sin marco claro)", () => {
        expect(css).toMatch(/grid-template-areas:\s*"rail main side"/);
        expect(css).toContain("--rail-width: 92px");
        expect(css).toContain("--sidebar-width: 364px");
        expect(css).not.toContain("--container-max");
    });

    it("el body tiene fondo oscuro (sin marco blanco)", () => {
        const bodyRule = css.match(/(^|\n)\s*body\s*\{[^}]*\}/);
        expect(bodyRule).toBeTruthy();
        expect(bodyRule[0]).toContain("background");
        expect(bodyRule[0]).toContain("--bg-main");
    });

    it("scrollbar global única para todos los contenedores", () => {
        expect(css).toContain("scrollbar-width: thin");
        expect(css).toContain("::-webkit-scrollbar-thumb");
        expect((css.match(/scrollbar-width:/g) ?? []).length).toBe(1);
    });

    it("paneles sin borde; secciones con divisor fino", () => {
        const panelRule = css.match(/\.panel-card\s*\{[^}]*\}/);
        expect(panelRule).not.toBeNull();
        expect(panelRule[0]).not.toContain("border:");
        expect(css).toContain(
            "border-top: 1px solid var(--divider)"
        );
    });

    it("media queries solo en responsive.css (importado el último)", () => {
        const files = loadCssFiles();
        const last = files[files.length - 1];

        expect(last.name).toBe("responsive.css");

        for (const file of files.slice(0, -1)) {
            expect(file.content).not.toContain("@media");
        }

        expect(last.content).toMatch(/@media \(max-width: 1300px\)/);
        expect(last.content).toMatch(/@media \(max-width: 1050px\)/);
        expect(last.content).toMatch(/@media \(max-width: 700px\)/);
    });

    it("sidebar sticky de viewport con scroll interno (sin hueco vacío)", () => {
        const sidebarRule = css.match(/(^|\n)\s*\.sidebar\s*\{[^}]*\}/);
        expect(sidebarRule).not.toBeNull();
        expect(sidebarRule[0]).toContain("position: sticky");
        expect(sidebarRule[0]).toContain("align-self: start");
        expect(sidebarRule[0]).toContain("height: 100vh");
        expect(sidebarRule[0]).toContain("overflow-y: auto");

        const files = loadCssFiles();
        const responsive = files.find((file) => file.name === "responsive.css");
        const stackedRule = responsive.content.match(
            /(^|\n)\s*\.sidebar\s*\{[^}]*\}/
        );
        expect(stackedRule).not.toBeNull();
        expect(stackedRule[0]).toContain("position: static");
        expect(stackedRule[0]).toContain("height: auto");
        expect(stackedRule[0]).toContain("overflow: visible");
    });

    it("sin !important (auditoría #11)", () => {
        expect(css).not.toContain("!important");
    });

    it("marcadores de equity con tokens, sin hex sueltos (009 RF-7/RF-8)", () => {
        const rule = css.match(/\.equity-marker\s*\{[^}]+\}/);
        expect(rule).not.toBeNull();
        expect(rule[0]).toContain("var(--orange)");
        expect(rule[0]).toContain("var(--text-primary)");
        expect(rule[0]).toContain("cursor: pointer");
        expect(rule[0]).not.toMatch(/#[0-9a-fA-F]{3,8}/);
    });
});
