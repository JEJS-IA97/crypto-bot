import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import KnowledgeCard from "../KnowledgeCard";

const KNOWLEDGE = {
    id: 1,
    hypothesis_id: 2,
    statement: "ORB funciona en aperturas de alta volatilidad",
    evidence_json:
        '{"confidence": "0.8", "sample_size": 5, "favorable": 4}',
    sample_size: 5,
    confidence_interval_json: '{"low": "0.3755", "high": "1.0"}',
    works_when_json: "null",
    fails_when_json: "null",
    validated_at: "2026-10-02T09:00:00Z",
    version: 1,
    observed_impact: "+2.1% en paper",
    status: "ACTIVE",
    rollback_reason: null,
    deprecated_at: null,
    created_at: "2026-10-02T09:00:00Z",
};

describe("KnowledgeCard (RF-7)", () => {
    afterEach(cleanup);

    it("muestra la afirmación, el nº de casos y el estado reales", () => {
        render(<KnowledgeCard knowledge={KNOWLEDGE} />);

        expect(
            screen.getByText(
                "ORB funciona en aperturas de alta volatilidad"
            )
        ).toBeInTheDocument();
        expect(screen.getByText("5")).toBeInTheDocument();
        expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    });

    it("parsea y muestra el intervalo de confianza", () => {
        render(<KnowledgeCard knowledge={KNOWLEDGE} />);

        expect(screen.getByText(/0\.3755/)).toBeInTheDocument();
        expect(screen.getByText(/1\.0/)).toBeInTheDocument();
    });

    it("muestra la fecha de validación y el efecto observado", () => {
        render(<KnowledgeCard knowledge={KNOWLEDGE} />);

        expect(
            screen.getByText("2026-10-02T09:00:00Z")
        ).toBeInTheDocument();
        expect(
            screen.getByText("+2.1% en paper")
        ).toBeInTheDocument();
    });

    it("sin rollback no inventa motivo; con rollback lo muestra", () => {
        const { unmount } = render(
            <KnowledgeCard knowledge={KNOWLEDGE} />
        );
        expect(
            screen.queryByText(/rollback/i)
        ).not.toBeInTheDocument();
        unmount();

        const deprecada = {
            ...KNOWLEDGE,
            status: "DEPRECATED",
            rollback_reason: "contradicciones en paper reciente",
            deprecated_at: "2026-10-05T12:00:00Z",
        };
        render(<KnowledgeCard knowledge={deprecada} />);

        expect(
            screen.getByText(
                "contradicciones en paper reciente"
            )
        ).toBeInTheDocument();
        expect(screen.getByText("DEPRECATED")).toBeInTheDocument();
        expect(
            screen.getByText("2026-10-05T12:00:00Z")
        ).toBeInTheDocument();
    });

    it("evidence_json malformado no rompe la tarjeta", () => {
        const rota = { ...KNOWLEDGE, evidence_json: "no-es-json" };
        render(<KnowledgeCard knowledge={rota} />);

        expect(
            screen.getByText(
                "ORB funciona en aperturas de alta volatilidad"
            )
        ).toBeInTheDocument();
    });
});
