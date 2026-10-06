import { formatMoney } from "../utils/format";

/* Tonos por activo (design.json live_prices: un color por cripto).
   Sin sparkline: no existe serie por activo → sería dato falso. */
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

function baseSymbol(symbol) {
    return symbol.replace(/USDT$/, "");
}

function LivePrices({ prices }) {
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

                                <span className="price-value">
                                    ${formatMoney(price.price_usd)}
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
