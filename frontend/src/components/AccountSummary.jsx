import { formatMoney } from "../utils/format";

const ICONS = {
    wallet: (
        <path
            d="M3 7.5A2.5 2.5 0 0 1 5.5 5H18a2 2 0 0 1 2 2v1H5.5A2.5 2.5 0 0 1 3 7.5Zm0 0V17a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6H5.5a2.5 2.5 0 0 1 0-5"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    ),
    invested: (
        <path
            d="M4 20V10m6 10V4m6 16v-7"
            strokeLinecap="round"
        />
    ),
    up: (
        <path
            d="M4 16l5-5 3.5 3.5L20 7m0 0h-5m5 0v5"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    ),
    down: (
        <path
            d="M4 8l5 5 3.5-3.5L20 17m0 0h-5m5 0v-5"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    ),
};

function MetricTile({ tone, icon, label, value, valueClass }) {
    return (
        <div className="metric-tile">
            <span className={`metric-icon ${tone}`} aria-hidden="true">
                <svg
                    aria-hidden="true"
                    focusable="false"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                >
                    {ICONS[icon]}
                </svg>
            </span>

            <div className="metric-text">
                <span className="metric-label">{label}</span>

                <strong
                    className={
                        valueClass
                            ? `metric-value ${valueClass}`
                            : "metric-value"
                    }
                >
                    {value}
                </strong>
            </div>
        </div>
    );
}

function AccountSummary({ account, balance }) {
    const availableBalance = balance.available_usd || 0;
    const totalBalance = balance.total_balance_usd || 0;
    const investedBalance = balance.invested_usd || 0;
    const marketValue = balance.market_value_usd || 0;
    const realizedPnl = balance.realized_pnl_usd || 0;
    const unrealizedPnl = balance.unrealized_pnl_usd || 0;

    const realizedClass =
        Number(realizedPnl) >= 0 ? "value-positive" : "value-negative";
    const unrealizedClass =
        Number(unrealizedPnl) >= 0 ? "value-positive" : "value-negative";

    return (
        <section
            className="summary-row"
            aria-label="Resumen de la cuenta"
        >
            <div className="summary-group">
                <MetricTile
                    tone="tone-accent"
                    icon="wallet"
                    label="Disponible"
                    value={`$${formatMoney(availableBalance)}`}
                />

                <MetricTile
                    tone="tone-purple"
                    icon="invested"
                    label="Invertido"
                    value={`$${formatMoney(investedBalance)}`}
                />
            </div>

            <article className="account-card">
                <span className="eyebrow">Cuenta activa</span>

                <h2>{account.name}</h2>

                <span className="account-id">
                    ID: {account.id} · SIMULACIÓN
                </span>

                <strong className="account-total">
                    ${formatMoney(totalBalance)}
                </strong>

                <span className="account-total-label">
                    Balance total
                </span>

                <div className="account-sub">
                    <span>Valor de mercado</span>

                    <strong>
                        ${formatMoney(marketValue)}
                    </strong>
                </div>
            </article>

            <div className="summary-group">
                <MetricTile
                    tone="tone-cyan"
                    icon="up"
                    label="PnL realizado"
                    value={`$${formatMoney(realizedPnl)}`}
                    valueClass={realizedClass}
                />

                <MetricTile
                    tone="tone-blue"
                    icon="down"
                    label="PnL no realizado"
                    value={`$${formatMoney(unrealizedPnl)}`}
                    valueClass={unrealizedClass}
                />
            </div>
        </section>
    );
}

export default AccountSummary;
