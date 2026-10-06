import { useState } from "react";

import { sendExternalSignal } from "../api/signals";

const SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "LINKUSDT",
];

function ExternalSignalForm() {
    const [symbol, setSymbol] = useState("BTCUSDT");
    const [side, setSide] = useState("BUY");
    const [priceLimit, setPriceLimit] = useState("");
    const [quantity, setQuantity] = useState("");
    const [source, setSource] = useState("panel");
    const [busy, setBusy] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState("");

    const handleSubmit = async (event) => {
        event.preventDefault();

        if (priceLimit && Number(priceLimit) <= 0) {
            setError("El precio debe ser mayor que cero.");
            setResult(null);
            return;
        }

        if (quantity && Number(quantity) <= 0) {
            setError("La cantidad debe ser mayor que cero.");
            setResult(null);
            return;
        }

        setBusy(true);
        setError("");
        setResult(null);

        try {
            const payload = { symbol, side, source };

            if (priceLimit) {
                payload.price_limit = priceLimit;
            }
            if (quantity) {
                payload.quantity = quantity;
            }

            const response = await sendExternalSignal(payload);
            setResult(response);

            if (response.estado !== "aceptada") {
                setError("");
            }
        } catch (requestError) {
            console.error("Error enviando la señal:", requestError);
            setError(
                requestError.response?.data?.detail ||
                    "No se pudo enviar la señal."
            );
        } finally {
            setBusy(false);
        }
    };

    return (
        <section
            className="external-signal panel-card"
            data-testid="external-signal"
        >
            <div className="panel-heading">
                <div>
                    <span className="eyebrow">SEÑAL EXTERNA</span>
                    <h2>Enviar señal copy</h2>
                </div>

                <span className="panel-caption">RF-8</span>
            </div>

            <form
                className="signal-form"
                onSubmit={handleSubmit}
                noValidate
            >
                <div className="order-fields-grid">
                    <div className="field-group">
                        <label htmlFor="signal-symbol">Par</label>
                        <select
                            id="signal-symbol"
                            value={symbol}
                            onChange={(event) =>
                                setSymbol(event.target.value)
                            }
                        >
                            {SYMBOLS.map((item) => (
                                <option key={item} value={item}>
                                    {item}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="field-group">
                        <label htmlFor="signal-side">Lado</label>
                        <select
                            id="signal-side"
                            value={side}
                            onChange={(event) =>
                                setSide(event.target.value)
                            }
                        >
                            <option value="BUY">BUY</option>
                            <option value="SELL">SELL</option>
                        </select>
                    </div>

                    <div className="field-group">
                        <label htmlFor="signal-price">
                            Precio límite
                        </label>
                        <input
                            id="signal-price"
                            type="number"
                            min="0"
                            step="any"
                            placeholder="mercado"
                            value={priceLimit}
                            onChange={(event) =>
                                setPriceLimit(event.target.value)
                            }
                        />
                    </div>

                    <div className="field-group">
                        <label htmlFor="signal-quantity">Cantidad</label>
                        <input
                            id="signal-quantity"
                            type="number"
                            min="0"
                            step="any"
                            placeholder="automática"
                            value={quantity}
                            onChange={(event) =>
                                setQuantity(event.target.value)
                            }
                        />
                    </div>

                    <div className="field-group">
                        <label htmlFor="signal-source">Fuente</label>
                        <input
                            id="signal-source"
                            type="text"
                            value={source}
                            onChange={(event) =>
                                setSource(event.target.value)
                            }
                        />
                    </div>
                </div>

                {error && (
                    <div className="form-message error">{error}</div>
                )}

                {result && (
                    <div
                        className={`form-message ${
                            result.estado === "aceptada"
                                ? "success"
                                : "error"
                        }`}
                        data-testid="signal-result"
                    >
                        {result.estado === "aceptada"
                            ? `Aceptada — ${result.symbol} ${
                                  result.side
                              }${
                                  result.quantity
                                      ? ` — cantidad ${result.quantity}`
                                      : ""
                              }`
                            : `Rechazada — motivo: ${
                                  result.motivo || "desconocido"
                              }`}
                    </div>
                )}

                <button
                    type="submit"
                    className="execute-button buy-button"
                    disabled={busy}
                >
                    {busy ? "Enviando..." : "Enviar señal"}
                </button>
            </form>
        </section>
    );
}

export default ExternalSignalForm;
