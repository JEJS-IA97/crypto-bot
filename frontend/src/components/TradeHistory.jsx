import { formatDateTime, formatMoney } from "../utils/format";

function TradeHistory({ trades }) {
    return (
        <section className="data-section">
            <div className="section-header">
                <div>
                    <span className="eyebrow">
                        TRADE HISTORY
                    </span>

                    <h2>Historial de operaciones</h2>
                </div>
            </div>

            {trades.length === 0 ? (
                <div className="empty-state table-empty-state">
                    <span
                        className="empty-state-icon"
                        aria-hidden="true"
                    >
                        ▤
                    </span>

                    <span>
                        Todavía no hay operaciones.
                    </span>
                </div>
            ) : (
                <div className="data-table-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Fecha</th>
                                <th>Activo</th>
                                <th>Tipo</th>
                                <th>Cantidad</th>
                                <th>Precio</th>
                                <th>Total</th>
                                <th>Comisión</th>
                            </tr>
                        </thead>

                        <tbody>
                            {trades.map((trade) => (
                                <tr key={trade.id}>
                                    <td>
                                        {formatDateTime(trade.executed_at)}
                                    </td>

                                    <td>
                                        <strong>{trade.symbol}</strong>
                                    </td>

                                    <td
                                        className={
                                            trade.side === "BUY"
                                                ? "value-positive"
                                                : "value-negative"
                                        }
                                    >
                                        {trade.side === "BUY"
                                            ? "Compra"
                                            : "Venta"}
                                    </td>

                                    <td>{trade.quantity}</td>

                                    <td>
                                        ${formatMoney(trade.price)}
                                    </td>

                                    <td>
                                        ${formatMoney(trade.total_usd)}
                                    </td>

                                    <td>
                                        ${formatMoney(trade.fee_usd)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    );
}

export default TradeHistory;
