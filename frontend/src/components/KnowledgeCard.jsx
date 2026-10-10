function safeParse(json) {
    try {
        return JSON.parse(json);
    } catch {
        return null;
    }
}

function KnowledgeCard({ knowledge }) {
    const evidence = safeParse(knowledge.evidence_json);
    const interval = safeParse(knowledge.confidence_interval_json);

    return (
        <article className="knowledge-card">
            <header className="knowledge-card-header">
                <span className="knowledge-status">
                    {knowledge.status}
                </span>
            </header>

            <p className="knowledge-statement">
                {knowledge.statement}
            </p>

            <dl className="knowledge-metrics">
                <div>
                    <dt>Casos</dt>
                    <dd>{knowledge.sample_size}</dd>
                </div>

                {evidence?.confidence ? (
                    <div>
                        <dt>Confianza</dt>
                        <dd>{evidence.confidence}</dd>
                    </div>
                ) : null}

                {interval ? (
                    <div>
                        <dt>Intervalo</dt>
                        <dd>
                            <span>{interval.low}</span>
                            {" – "}
                            <span>{interval.high}</span>
                        </dd>
                    </div>
                ) : null}
            </dl>

            <footer className="knowledge-card-footer">
                {knowledge.validated_at ? (
                    <time dateTime={knowledge.validated_at}>
                        Confirmado:{" "}
                        <span>{knowledge.validated_at}</span>
                    </time>
                ) : null}

                {knowledge.observed_impact ? (
                    <p className="knowledge-impact">
                        {knowledge.observed_impact}
                    </p>
                ) : null}
            </footer>

            {knowledge.rollback_reason ? (
                <p className="knowledge-rollback">
                    Rollback:{" "}
                    <strong>{knowledge.rollback_reason}</strong>
                    {knowledge.deprecated_at ? (
                        <>
                            {" "}
                            (<time
                                dateTime={knowledge.deprecated_at}
                            >
                                {knowledge.deprecated_at}
                            </time>
                            )
                        </>
                    ) : null}
                </p>
            ) : null}
        </article>
    );
}

export default KnowledgeCard;
