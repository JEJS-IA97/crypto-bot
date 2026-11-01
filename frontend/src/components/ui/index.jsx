/** Piezas visuales comunes del panel: tarjeta, cifra, esqueleto de carga y estado vacío. */

export function Card({ title, aside, children, className = "", pad = true }) {
    return (
        <section className={`ui-card ${pad ? "" : "flush"} ${className}`}>
            {(title || aside) && (
                <header className="ui-card-head">
                    {title && <h2>{title}</h2>}
                    {aside && <div className="ui-card-aside">{aside}</div>}
                </header>
            )}
            {children}
        </section>
    );
}

export function Stat({ label, value, sub, tone = "", big = false }) {
    return (
        <div className={`ui-stat ${big ? "big" : ""}`}>
            <span className="ui-stat-label">{label}</span>
            <span className={`ui-stat-value num ${tone}`}>{value}</span>
            {sub && <span className={`ui-stat-sub ${tone}`}>{sub}</span>}
        </div>
    );
}

export function Skeleton({ lines = 3, height = 14, block = 0 }) {
    return (
        <div className="ui-skel" aria-busy="true" aria-label="Cargando">
            {block > 0 && <div className="ui-skel-bar" style={{ height: block }} />}
            {Array.from({ length: lines }, (_, i) => (
                <div key={i} className="ui-skel-bar" style={{ height, width: `${90 - ((i * 17) % 40)}%` }} />
            ))}
        </div>
    );
}

export function Empty({ icon: Icon, title, children }) {
    return (
        <div className="ui-empty">
            {Icon && <Icon size={22} strokeWidth={1.5} aria-hidden="true" />}
            <strong>{title}</strong>
            {children && <p>{children}</p>}
        </div>
    );
}

export function Badge({ tone = "", children, title }) {
    return (
        <span className={`ui-badge ${tone}`} title={title}>
            {children}
        </span>
    );
}

export function PageHead({ title, subtitle, children }) {
    return (
        <header className="ui-page-head">
            <div>
                <h1>{title}</h1>
                {subtitle && <p>{subtitle}</p>}
            </div>
            {children && <div className="ui-page-actions">{children}</div>}
        </header>
    );
}
