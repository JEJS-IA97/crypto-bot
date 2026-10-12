import { formatMoney } from "../utils/format";

/* Tonos por activo (design.json live_prices: un color por cripto).
   Los datos de la sparkline vienen del historial real del panel. */
const COIN_TONES = {
    BTC: "coin-orange",
    ETH: "coin-cyan",
    BNB: "coin-blue",
    SOL: "coin-purple",
    XRP: "coin-blue",
    DOGE: "coin-orange",
    ADA: "coin-purple",
    LINK: "coin-cyan",
    LTC: "coin-blue",
};

// % respecto al precio de hace un minuto (60 ticks de 1 s).
const CHANGE_WINDOW = 60;

function baseSymbol(symbol) {
    return symbol.replace(/USDT$/, "");
}

function priceChange(points) {
    if (!Array.isArray(points) || points.length < 2) {
        return null;
    }

    const current = points[points.length - 1];
    const reference =
        points[Math.max(0, points.length - 1 - CHANGE_WINDOW)];

    if (!Number.isFinite(current) || !reference) {
        return null;
    }

    return ((current - reference) / reference) * 100;
}

function Sparkline({ points }) {
    if (!Array.isArray(points) || points.length < 2) {
        return <span className="price-spark" aria-hidden="true" />;
    }

    const min = Math.min(...points);
    const max = Math.max(...points);
    const span = max - min || 1;
    const width = 64;
    const height = 20;
    const step =
        points.length > 1 ? width / (points.length - 1) : 0;
    const rising = points[points.length - 1] >= points[0];

    const coords = points
        .map(
            (value, index) =>
                `${index * step},${((max - value) / span) * (height - 2) + 1}`
        )
        .join(" ");

    return (
        <svg
            className={`price-spark ${rising ? "price-spark-up" : "price-spark-down"}`}
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
        >
            <polyline points={coords} fill="none" />
        </svg>
    );
}

function LivePrices({ prices, priceHistory = {} }) {
    const rows = Array.isArray(prices) ? prices : [];

    return (
        <section aria-labelledby="live-prices-title">
            <h3 className="sidebar-heading" id="live-prices-title">
                Precios en vivo
            </h3>

            {rows.length === 0 ? (
                <div className="empty-state">
                    <span
                        className="empty-state-icon"
                        aria-hidden="true"
                    >
                        ?
                    </span>

                    <span>Sin precios de mercado.</span>
                </div>
            ) : (
                <ul className="price-list">
                    {rows.map((price) => {
                        const base = baseSymbol(price.symbol);
                        const points = priceHistory[price.symbol] || [];
                        const change = priceChange(points);
                        const rising = (change ?? 0) >= 0;

                        return (
                            <li
                                className="price-row"
                                key={price.symbol}
                            >
                                <span
                                    className={`price-coin ${
                                        COIN_TONES[base] || "coin-blue"
                                    }`}
                                    aria-hidden="true"
                                >
                                    {base.charAt(0)}
                                </span>

                                <div className="price-name">
                                    <strong>{base}</strong>

                                    <span className="price-quote">
                                        USDT
                                    </span>
                                </div>

                                <Sparkline points={points} />

                                <span
                                    className={`price-value ${
                                        rising
                                            ? "value-positive"
                                            : "value-negative"
                                    }`}
                                >
                                    ${formatMoney(price.price_usd)}

                                    {change !== null && (
                                        <span className="price-delta">
                                            {rising ? "▲" : "▼"}{" "}
                                            {Math.abs(change).toFixed(2)}
                                            %
                                        </span>
                                    )}
                                </span>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}

export default LivePrices;
