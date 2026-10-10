import { useCallback, useEffect, useState } from "react";

import HypothesisCard from "./HypothesisCard";
import KnowledgeCard from "./KnowledgeCard";
import {
    evaluateHypothesis,
    getHypotheses,
    getKnowledge,
    transitionHypothesis,
} from "../api/learning";

const POLL_MS = 5000;

const TRANSITIONS = {
    PROPOSED: [{ to: "TESTING", label: "Pasar a TESTING" }],
    TESTING: [],
    VALIDATED: [
        {
            to: "ACTIVE",
            label: "Promover a conocimiento",
            needsReason: true,
        },
    ],
    ACTIVE: [
        {
            to: "DEPRECATED",
            label: "Retirar (rollback)",
            needsReason: true,
        },
    ],
    DEPRECATED: [],
    REJECTED: [],
};

function LearningTab({ minCases = 30 }) {
    const [hypotheses, setHypotheses] = useState([]);
    const [knowledge, setKnowledge] = useState([]);
    const [busy, setBusy] = useState(false);

    const refresh = useCallback(async () => {
        const [hypoRows, knowledgeRows] = await Promise.all([
            getHypotheses(),
            getKnowledge(),
        ]);
        setHypotheses(Array.isArray(hypoRows) ? hypoRows : []);
        setKnowledge(
            Array.isArray(knowledgeRows) ? knowledgeRows : []
        );
    }, []);

    useEffect(() => {
        // refresh() es async: ningún setState ocurre de forma
        // síncrona dentro del effect (falso positivo de la regla).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        refresh();
        const timer = setInterval(refresh, POLL_MS);
        return () => clearInterval(timer);
    }, [refresh]);

    const handleEvaluate = async (hypothesis) => {
        if (
            !window.confirm(
                `¿Evaluar la hipótesis #${hypothesis.id}?`
            )
        ) {
            return;
        }
        setBusy(true);
        try {
            await evaluateHypothesis(hypothesis.id);
            await refresh();
        } finally {
            setBusy(false);
        }
    };

    const handleTransition = async (hypothesis, transition) => {
        const payload = { to: transition.to };
        if (transition.needsReason) {
            const reason = window.prompt(
                "Motivo de la transición:"
            );
            if (!reason || !reason.trim()) {
                return;
            }
            payload.reason = reason.trim();
        }
        if (!window.confirm(`¿${transition.label}?`)) {
            return;
        }
        setBusy(true);
        try {
            await transitionHypothesis(hypothesis.id, payload);
            await refresh();
        } finally {
            setBusy(false);
        }
    };

    return (
        <section className="learning-tab" aria-label="Learning">
            <div className="learning-columns">
                <div className="learning-column">
                    <div className="section-header">
                        <div>
                            <span className="eyebrow">
                                HIPÓTESIS
                            </span>

                            <h2>Lo que va aprendiendo</h2>
                        </div>
                    </div>

                    {hypotheses.length === 0 ? (
                        <div className="empty-state">
                            Aún no hay hipótesis.
                        </div>
                    ) : (
                        <div className="learning-cards">
                            {hypotheses.map((hypothesis) => (
                                <div
                                    key={hypothesis.id}
                                    className="learning-item"
                                >
                                    <HypothesisCard
                                        hypothesis={hypothesis}
                                        minCases={minCases}
                                    />

                                    <div className="learning-actions">
                                        {hypothesis.status ===
                                        "TESTING" ? (
                                            <button
                                                type="button"
                                                className="btn btn-utility"
                                                disabled={busy}
                                                onClick={() =>
                                                    handleEvaluate(
                                                        hypothesis
                                                    )
                                                }
                                            >
                                                Evaluar
                                            </button>
                                        ) : null}

                                        {(
                                            TRANSITIONS[
                                                hypothesis
                                                    .status
                                            ] ?? []
                                        ).map((transition) => (
                                            <button
                                                key={
                                                    transition.to
                                                }
                                                type="button"
                                                className="btn btn-secondary"
                                                disabled={busy}
                                                onClick={() =>
                                                    handleTransition(
                                                        hypothesis,
                                                        transition
                                                    )
                                                }
                                            >
                                                {
                                                    transition.label
                                                }
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="learning-column">
                    <div className="section-header">
                        <div>
                            <span className="eyebrow">
                                CONOCIMIENTO
                            </span>

                            <h2>Lo que ha aprendido</h2>
                        </div>
                    </div>

                    {knowledge.length === 0 ? (
                        <div className="empty-state">
                            Aún no hay conocimiento confirmado.
                        </div>
                    ) : (
                        <div className="learning-cards">
                            {knowledge.map((row) => (
                                <KnowledgeCard
                                    key={row.id}
                                    knowledge={row}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}

export default LearningTab;
