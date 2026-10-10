import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import HypothesisCard from "../HypothesisCard";

const HYPOTHESIS = {
    id: 1,
    statement: "Funding extremo anticipa reversiones",
    source: "operator",
    case_count: 12,
    favorable_cases: 8,
    unfavorable_cases: 4,
    confidence: "0.666667",
    status: "TESTING",
    version: 2,
    evaluation_note: "muestra insuficiente: 12/30",
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-10-01T10:00:00Z",
};

describe("HypothesisCard (RF-7)", () => {
    afterEach(cleanup);

    it("muestra statement, source, estado, casos y confianza reales", () => {
        render(<HypothesisCard hypothesis={HYPOTHESIS} minCases={30} />);

        expect(
            screen.getByText("Funding extremo anticipa reversiones")
        ).toBeInTheDocument();
        expect(screen.getByText("operator")).toBeInTheDocument();
        expect(screen.getByText("TESTING")).toBeInTheDocument();
        expect(screen.getByText("8")).toBeInTheDocument();
        expect(screen.getByText("4")).toBeInTheDocument();
        expect(screen.getByText("0.666667")).toBeInTheDocument();
    });

    it("expone el umbral activo y los casos faltantes (max(0, umbral − casos))", () => {
        render(<HypothesisCard hypothesis={HYPOTHESIS} minCases={30} />);

        expect(screen.getByText("18")).toBeInTheDocument();
        expect(
            screen.getByText(/umbral/)
        ).toHaveTextContent("30");
    });

    it("sin casos faltantes no muestra contador de faltantes", () => {
        const completa = {
            ...HYPOTHESIS,
            case_count: 30,
            favorable_cases: 20,
            unfavorable_cases: 10,
        };
        render(<HypothesisCard hypothesis={completa} minCases={30} />);

        expect(
            screen.queryByText(/faltan/i)
        ).not.toBeInTheDocument();
    });

    it("muestra la nota de evaluación si existe y no la inventa si falta", () => {
        const { unmount } = render(
            <HypothesisCard hypothesis={HYPOTHESIS} minCases={30} />
        );
        expect(
            screen.getByText("muestra insuficiente: 12/30")
        ).toBeInTheDocument();
        unmount();

        const sinNota = { ...HYPOTHESIS, evaluation_note: null };
        render(
            <HypothesisCard hypothesis={sinNota} minCases={30} />
        );
        expect(
            screen.queryByText(/muestra insuficiente/)
        ).not.toBeInTheDocument();
    });

    it("sin confianza no inventa un valor numérico", () => {
        const sinConfianza = { ...HYPOTHESIS, confidence: null };
        render(
            <HypothesisCard hypothesis={sinConfianza} minCases={30} />
        );

        expect(screen.queryByText("0.000000")).not.toBeInTheDocument();
        expect(screen.getByText(/sin confianza/i)).toBeInTheDocument();
    });

    it("muestra la fecha de última actualización visible", () => {
        render(<HypothesisCard hypothesis={HYPOTHESIS} minCases={30} />);

        expect(
            screen.getByText("2026-10-01T10:00:00Z")
        ).toBeInTheDocument();
    });
});
