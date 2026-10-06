import { readFileSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

import { describe, expect, it } from "vitest";

import { loadCss } from "./css";

const css = loadCss();

const jsxFiles = [
  "src/components/ExternalSignalForm.jsx",
  "src/components/KillSwitch.jsx",
  "src/components/TokenField.jsx",
  "src/components/TradingPanel.jsx",
];

describe("action hierarchy (spec 003, RF-2)", () => {
  it("define las cuatro variantes de jerarquía", () => {
    for (const variant of [
      ".btn-primary",
      ".btn-secondary",
      ".btn-danger",
      ".btn-utility",
    ]) {
      expect(css).toContain(variant);
    }
  });

  it("los botones y tabs comparten foco visible", () => {
    expect(css).toMatch(/\.btn:focus-visible/);
    expect(css).toMatch(/\.side-tab:focus-visible/);
    expect(css).toMatch(/button:focus-visible/);
    const rule = css.match(/button:focus-visible[^{]*\{[^}]+\}/);
    expect(rule).not.toBeNull();
    expect(rule[0]).toContain("outline");
  });

  it("estados disabled en base y tabs", () => {
    expect(css).toMatch(/\.btn:disabled/);
    expect(css).toMatch(/\.side-tab:disabled/);
  });

  it("un solo verde de acción (token único, sin hex sueltos)", () => {
    expect((css.match(/--color-buy:/g) ?? []).length).toBe(1);
    expect((css.match(/#00bd72/g) ?? []).length).toBe(0);
    expect((css.match(/#00b96e/g) ?? []).length).toBe(0);
  });

  it("tabs y botones usan el mismo token de acción", () => {
    const buyTab = css.match(/\.side-tab\.active\.buy-tab\s*\{[^}]+\}/);
    expect(buyTab).not.toBeNull();
    expect(buyTab[0]).toContain("var(--color-buy)");
    const primary = css.match(/\.btn-primary[^{]*\{[^}]+\}/);
    expect(primary).not.toBeNull();
    expect(primary[0]).toContain("var(--color-buy)");
  });

  it("el JSX ya no usa la clase legada execute-button", () => {
    for (const file of jsxFiles) {
      const source = readFileSync(join(process.cwd(), file), "utf8");
      expect(source).not.toContain("execute-button");
    }
  });
});
