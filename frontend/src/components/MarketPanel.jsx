import { useEffect, useState } from "react";
import { updateMarketPrice } from "../api/simulation";

const DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
];

function formatMoney(value) {
    return Number(value || 0).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 8,
    });
}

function MarketPanel({
    marketPrices,
    onMarketPriceUpdated,
}) {
    const [inputPrices, setInputPrices] = useState({});
    const [savingSymbol, setSavingSymbol] = useState("");
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        const nextPrices = {};

        DEFAULT_SYMBOLS.forEach((symbol) => {
            const marketPrice = marketPrices.find(
                (item) => item.symbol === symbol
            );

            nextPrices[symbol] = marketPrice
                ? marketPrice.price_usd
                : "";
        });

        setInputPrices(nextPrices);
    }, [marketPrices]);

    const handleInputChange = (symbol, value) => {
        setInputPrices((currentPrices) => ({
            ...currentPrices,
            [symbol]: value,
        }));
    };

    const handleSavePrice = async (symbol) => {
        const nextPrice = inputPrices[symbol];

        if (!nextPrice || Number(nextPrice) <= 0) {
            setError("El precio debe ser mayor que cero.");
            setMessage("");
            return;
        }

        try {
            setSavingSymbol(symbol);
            setError("");
            setMessage("");

            await updateMarketPrice({
                symbol,
                price_usd: String(nextPrice),
            });

            setMessage(`Precio de ${symbol} actualizado.`);

            if (onMarketPriceUpdated) {
                await onMarketPriceUpdated();
            }
        } catch (requestError) {
            console.error(
                "Error actualizando precio:",
                requestError
            );

            const detail = requestError.response?.data?.detail;

            setError(
                detail ||
                    "No se pudo actualizar el precio."
            );
        } finally {
            setSavingSymbol("");
        }
    };

    return (
        <section className="market-panel panel-card">
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">
                        MARKET DATA
                    </span>

                    <h2>Activos de simulación</h2>
                </div>

                <span className="panel-caption">
                    PRECIOS MANUALES
                </span>
            </div>

            {error && (
                <div className="form-message error">
                    {error}
                </div>
            )}

            {message && (
                <div className="form-message success">
                    {message}
                </div>
            )}

            <div className="market-table-wrapper">
                <table className="market-table">
                    <thead>
                        <tr>
                            <th>Activo</th>
                            <th>Precio actual</th>
                            <th>Nuevo precio</th>
                            <th>Acción</th>
                        </tr>
                    </thead>

                    <tbody>
                        {DEFAULT_SYMBOLS.map((symbol) => {
                            const marketPrice = marketPrices.find(
                                (item) => item.symbol === symbol
                            );

                            const currentPrice = marketPrice
                                ? marketPrice.price_usd
                                : 0;

                            return (
                                <tr key={symbol}>
                                    <td>
                                        <strong>{symbol}</strong>
                                    </td>

                                    <td>
                                        ${formatMoney(currentPrice)}
                                    </td>

                                    <td>
                                        <div className="price-input">
                                            <span>$</span>

                                            <input
                                                type="number"
                                                min="0"
                                                step="any"
                                                value={
                                                    inputPrices[symbol] || ""
                                                }
                                                onChange={(event) =>
                                                    handleInputChange(
                                                        symbol,
                                                        event.target.value
                                                    )
                                                }
                                            />
                                        </div>
                                    </td>

                                    <td>
                                        <button
                                            type="button"
                                            className="save-price-button"
                                            onClick={() =>
                                                handleSavePrice(symbol)
                                            }
                                            disabled={
                                                savingSymbol === symbol
                                            }
                                        >
                                            {savingSymbol === symbol
                                                ? "..."
                                                : "Guardar"}
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>

                <div className="market-note">
                    <span className="market-note-icon">i</span>

                    <span>
                        Los precios se utilizan únicamente para
                        calcular el valor de las posiciones en modo
                        simulación.
                        <br />
                        No representan órdenes reales de mercado.
                    </span>
                </div>
            </div>
        </section>
    );
}

export default MarketPanel;