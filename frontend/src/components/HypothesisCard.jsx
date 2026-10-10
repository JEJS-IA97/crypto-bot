function HypothesisCard({ hypothesis, minCases = 30 }) {
    const threshold = Number(minCases);
    const missing = Math.max(0, threshold - (hypothesis.case_count || 0));

    return (
        <article className="hypothesis-card">
            <header className="hypothesis-card-header">
                <span className="hypothesis-source">
                    {hypothesis.source}
                </span>

                <span className="hypothesis-status">
                    {hypothesis.status}
                </span>
            </header>

            <p className="hypothesis-statement">
                {hypothesis.statement}
            </p>

            <dl className="hypothesis-metrics">
                <div>
                    <dt>Casos</dt>
                    <dd>{hypothesis.case_count}</dd>
                </div>

                <div>
                    <dt>Favorables</dt>
                    <dd>{hypothesis.favorable_cases}</dd>
                </div>

                <div>
                    <dt>Desfavorables</dt>
                    <dd>{hypothesis.unfavorable_cases}</dd>
                </div>

                <div>
                    <dt>Confianza</dt>
                    <dd>
                        {hypothesis.confidence ?? "sin confianza"}
                    </dd>
                </div>
            </dl>

            {missing > 0 ? (
                <p className="hypothesis-missing">
                    Faltan <span>{missing}</span> casos
                    {" "}(umbral <span>{threshold}</span>)
                </p>
            ) : null}

            {hypothesis.evaluation_note ? (
                <p className="hypothesis-note">
                    {hypothesis.evaluation_note}
                </p>
            ) : null}

            <footer className="hypothesis-card-footer">
                <time dateTime={hypothesis.updated_at}>
                    {hypothesis.updated_at}
                </time>
            </footer>
        </article>
    );
}

export default HypothesisCard;
