import {
    act,
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";

import LearningTab from "../LearningTab";
import {
    evaluateHypothesis,
    getHypotheses,
    getKnowledge,
    transitionHypothesis,
} from "../../api/learning";

vi.mock("../../api/learning", () => ({
    getHypotheses: vi.fn(),
    getKnowledge: vi.fn(),
    createHypothesis: vi.fn(),
    transitionHypothesis: vi.fn(),
    evaluateHypothesis: vi.fn(),
    getStrategyVersions: vi.fn(),
}));

const HYPOTHESES = [
    {
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
    },
];

const KNOWLEDGE = [
    {
        id: 1,
        hypothesis_id: 2,
        statement: "ORB funciona en aperturas de alta volatilidad",
        evidence_json:
            '{"confidence": "0.8", "sample_size": 5, "favorable": 4}',
        sample_size: 5,
        confidence_interval_json:
            '{"low": "0.3755", "high": "1.0"}',
        validated_at: "2026-10-02T09:00:00Z",
        version: 1,
        observed_impact: null,
        status: "ACTIVE",
        rollback_reason: null,
        deprecated_at: null,
        created_at: "2026-10-02T09:00:00Z",
    },
];

async function flushPromises() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("LearningTab (RF-7)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getHypotheses.mockResolvedValue(HYPOTHESES);
        getKnowledge.mockResolvedValue(KNOWLEDGE);
    });

    afterEach(() => {
        cleanup();
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it("renderiza las dos columnas del talos", async () => {
        render(<LearningTab />);

        expect(
            screen.getByText("Lo que va aprendiendo")
        ).toBeInTheDocument();
        expect(
            screen.getByText("Lo que ha aprendido")
        ).toBeInTheDocument();
        await flushPromises();
    });

    it("estados vacíos honestos sin inventar datos", async () => {
        getHypotheses.mockResolvedValue([]);
        getKnowledge.mockResolvedValue([]);

        render(<LearningTab />);

        expect(
            await screen.findByText(/aún no hay hipótesis/i)
        ).toBeInTheDocument();
        expect(
            await screen.findByText(
                /aún no hay conocimiento confirmado/i
            )
        ).toBeInTheDocument();
    });

    it("carga datos al montar y refresca cada 5 s (polling)", async () => {
        vi.useFakeTimers();
        render(<LearningTab />);
        await act(async () => {
            await Promise.resolve();
        });

        expect(getHypotheses).toHaveBeenCalledTimes(1);
        expect(getKnowledge).toHaveBeenCalledTimes(1);

        await act(async () => {
            await vi.advanceTimersByTimeAsync(5000);
        });

        expect(getHypotheses).toHaveBeenCalledTimes(2);
        expect(getKnowledge).toHaveBeenCalledTimes(2);

        await act(async () => {
            await vi.advanceTimersByTimeAsync(5000);
        });

        expect(getHypotheses).toHaveBeenCalledTimes(3);
        expect(getKnowledge).toHaveBeenCalledTimes(3);
    });

    it("muestra las hipótesis y el conocimiento con timestamps", async () => {
        render(<LearningTab />);

        expect(
            await screen.findByText(
                "Funding extremo anticipa reversiones"
            )
        ).toBeInTheDocument();
        expect(
            await screen.findByText(
                "ORB funciona en aperturas de alta volatilidad"
            )
        ).toBeInTheDocument();
        expect(
            screen.getByText("2026-10-01T10:00:00Z")
        ).toBeInTheDocument();
        expect(
            screen.getByText("2026-10-02T09:00:00Z")
        ).toBeInTheDocument();
    });

    it("evaluar pide confirmación y llama al endpoint real (RF-4)", async () => {
        evaluateHypothesis.mockResolvedValue({
            ...HYPOTHESES[0],
        });
        const confirm = vi
            .spyOn(window, "confirm")
            .mockReturnValue(true);

        render(<LearningTab />);
        await screen.findByText(
            "Funding extremo anticipa reversiones"
        );

        fireEvent.click(
            screen.getByRole("button", { name: /evaluar/i })
        );

        expect(confirm).toHaveBeenCalled();
        await waitFor(() =>
            expect(evaluateHypothesis).toHaveBeenCalledWith(1)
        );
    });

    it("evaluar cancelado no llama al endpoint", async () => {
        vi.spyOn(window, "confirm").mockReturnValue(false);

        render(<LearningTab />);
        await screen.findByText(
            "Funding extremo anticipa reversiones"
        );

        fireEvent.click(
            screen.getByRole("button", { name: /evaluar/i })
        );

        expect(evaluateHypothesis).not.toHaveBeenCalled();
    });

    it("transición a TESTING pide confirmación y llama al endpoint real (RF-4)", async () => {
        const propuesta = {
            ...HYPOTHESES[0],
            id: 9,
            status: "PROPOSED",
        };
        getHypotheses.mockResolvedValue([propuesta]);
        transitionHypothesis.mockResolvedValue({
            ...propuesta,
            status: "TESTING",
        });
        const confirm = vi
            .spyOn(window, "confirm")
            .mockReturnValue(true);

        render(<LearningTab />);
        await screen.findByText(
            "Funding extremo anticipa reversiones"
        );

        fireEvent.click(
            screen.getByRole("button", {
                name: /pasar a testing/i,
            })
        );

        expect(confirm).toHaveBeenCalled();
        await waitFor(() =>
            expect(transitionHypothesis).toHaveBeenCalledWith(9, {
                to: "TESTING",
            })
        );
    });

    it("tras cada acción refresca las listas", async () => {
        evaluateHypothesis.mockResolvedValue(HYPOTHESES[0]);
        vi.spyOn(window, "confirm").mockReturnValue(true);

        render(<LearningTab />);
        await screen.findByText(
            "Funding extremo anticipa reversiones"
        );
        await flushPromises();
        const before = getHypotheses.mock.calls.length;

        fireEvent.click(
            screen.getByRole("button", { name: /evaluar/i })
        );

        await waitFor(() =>
            expect(getHypotheses.mock.calls.length).toBeGreaterThan(
                before
            )
        );
    });
});
