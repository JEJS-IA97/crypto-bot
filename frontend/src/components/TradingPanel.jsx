import { useEffect, useMemo, useState } from "react";
import { createOrder } from "../api/simulation";

const FEE_RATE = 0.001;

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

function getPriceForSymbol(marketPrices, symbol) {
    const marketPrice = marketPrices.find(
        (item) => item.symbol === symbol
    );

    return marketPrice ? Number(marketPrice.price_usd || 0) : 0;
}

function TradingPanel({
    accountId,
    marketPrices,
    positions,
    availableBalance,
    onOrderExecuted,
}) {
    const [side, setSide] = useState("BUY");
    const [symbol, setSymbol] = useState("BTCUSDT");
    const [quantity, setQuantity] = useState("");
    const [limitPrice, setLimitPrice] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    const currentPrice = useMemo(
        () => getPriceForSymbol(marketPrices, symbol),
        [marketPrices, symbol]
    );

    const selectedPosition = useMemo(
        () =>
            positions.find(
                (position) => position.symbol === symbol
            ),
        [positions, symbol]
    );

    const numericQuantity = Number(quantity || 0);
    const numericPrice = Number(limitPrice || currentPrice || 0);

    const subtotal = numericQuantity * numericPrice;
    const fee = subtotal * FEE_RATE;
    const estimatedTotal =
        side === "BUY" ? subtotal + fee : subtotal - fee;

    useEffect(() => {
        if (currentPrice > 0) {
            setLimitPrice(String(currentPrice));
        }
    }, [currentPrice]);

    const handleSideChange = (nextSide) => {
        setSide(nextSide);
        setMessage("");
        setError("");
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        setMessage("");
        setError("");

        if (!accountId) {
            setError("No hay una cuenta de simulación activa.");
            return;
        }

        if (!symbol) {
            setError("Selecciona un activo.");
            return;
        }

        if (numericQuantity <= 0) {
            setError("La cantidad debe ser mayor que cero.");
            return;
        }

        if (numericPrice <= 0) {
            setError("El precio debe ser mayor que cero.");
            return;
        }

        if (side === "BUY" && estimatedTotal > Number(availableBalance)) {
            setError(
                "No tienes suficiente balance disponible para esta compra."
            );
            return;
        }

        if (side === "SELL") {
            const positionQuantity = Number(
                selectedPosition?.quantity || 0
            );

            if (numericQuantity > positionQuantity) {
                setError(
                    "No tienes suficiente cantidad disponible para vender."
                );
                return;
            }
        }

        try {
            setSubmitting(true);

            await createOrder(accountId, {
                symbol,
                side,
                quantity: String(numericQuantity),
                price_usd: String(numericPrice),
            });

            setMessage(
                side === "BUY"
                    ? "Compra ejecutada correctamente."
                    : "Venta ejecutada correctamente."
            );

            setQuantity("");

            if (onOrderExecuted) {
                await onOrderExecuted();
            }
        } catch (requestError) {
            console.error(
                "Error ejecutando la operación:",
                requestError
            );

            const detail = requestError.response?.data?.detail;

            setError(
                detail ||
                    "No se pudo ejecutar la operación."
            );
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <section className="trading-panel panel-card">
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">
                        ORDER TERMINAL
                    </span>

                    <h2>Ejecutar operación</h2>
                </div>

                <span className="panel-status">
                    SIMULACIÓN
                </span>
            </div>

            <div className="trading-panel-content">
                <form
                    className="order-form"
                    onSubmit={handleSubmit}
                >
                    <div className="side-tabs">
                        <button
                            type="button"
                            className={
                                side === "BUY"
                                    ? "side-tab active buy-tab"
                                    : "side-tab"
                            }
                            onClick={() => handleSideChange("BUY")}
                        >
                            Comprar
                        </button>

                        <button
                            type="button"
                            className={
                                side === "SELL"
                                    ? "side-tab active sell-tab"
                                    : "side-tab"
                            }
                            onClick={() => handleSideChange("SELL")}
                        >
                            Vender
                        </button>
                    </div>

                    <div className="order-fields-grid">
                        <label className="field-group">
                            <span>Activo</span>

                            <select
                                value={symbol}
                                onChange={(event) =>
                                    setSymbol(event.target.value)
                                }
                            >
                                {DEFAULT_SYMBOLS.map((item) => (
                                    <option
                                        key={item}
                                        value={item}
                                    >
                                        {item}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="field-group">
                            <span>Precio actual</span>

                            <input
                                type="text"
                                value={
                                    currentPrice > 0
                                        ? `$${formatMoney(currentPrice)}`
                                        : "Sin precio"
                                }
                                readOnly
                            />
                        </label>

                        <label className="field-group">
                            <span>Cantidad</span>

                            <input
                                type="number"
                                min="0"
                                step="any"
                                placeholder="Ej. 0.01"
                                value={quantity}
                                onChange={(event) =>
                                    setQuantity(event.target.value)
                                }
                            />
                        </label>

                        <label className="field-group">
                            <span>Precio límite (USD)</span>

                            <input
                                type="number"
                                min="0"
                                step="any"
                                placeholder="Ej. 67432.10"
                                value={limitPrice}
                                onChange={(event) =>
                                    setLimitPrice(event.target.value)
                                }
                            />
                        </label>
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

                    <button
                        type="submit"
                        className={
                            side === "BUY"
                                ? "execute-button buy-button"
                                : "execute-button sell-button"
                        }
                        disabled={submitting}
                    >
                        {submitting
                            ? "Procesando..."
                            : side === "BUY"
                              ? "Ejecutar compra"
                              : "Ejecutar venta"}
                    </button>
                </form>

                <aside className="order-summary">
                    <div className="summary-heading">
                        <span>Resumen de la operación</span>
                    </div>

                    <div className="order-summary-row">
                        <span>Subtotal</span>
                        <strong>
                            ${formatMoney(subtotal)}
                        </strong>
                    </div>

                    <div className="order-summary-row">
                        <span>Comisión (0.1%)</span>
                        <strong>
                            ${formatMoney(fee)}
                        </strong>
                    </div>

                    <div className="summary-divider" />

                    <div className="order-summary-row total-row">
                        <span>Total estimado</span>
                        <strong>
                            ${formatMoney(estimatedTotal)}
                        </strong>
                    </div>

                    <div className="available-balance">
                        Disponible: $
                        {formatMoney(availableBalance)}
                    </div>
                </aside>
            </div>
        </section>
    );
}

export default TradingPanel;