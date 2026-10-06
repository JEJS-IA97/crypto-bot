import { formatMoney } from "../utils/format";

function OpenPositions({ positions }) {
    return (
        <section className="data-section">
            <div className="section-header">
                <div>
                    <span className="eyebrow">
                        OPEN POSITIONS
                    </span>

                    <h2>Posiciones abiertas</h2>
                </div>
            </div>

            {positions.length === 0 ? (
                <div className="empty-state table-empty-state">
                    <span
                        className="empty-state-icon"
                        aria-hidden="true"
                    >
                        ▣
                    </span>

                    <span>
                        No tienes posiciones abiertas.
                    </span>
                </div>
            ) : (
                <div className="data-table-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Activo</th>
                                <th>Cantidad</th>
                                <th>Precio promedio</th>
                                <th>Valor actual</th>
                                <th>PnL no realizado</th>
                            </tr>
                        </thead>

                        <tbody>
                            {positions.map((position) => (
                                <tr key={position.symbol}>
                                    <td>
                                        <strong>
                                            {position.symbol}
                                        </strong>
                                    </td>

                                    <td>
                                        {position.quantity}
                                    </td>

                                    <td>
                                        $
                                        {formatMoney(
                                            position.average_entry_price
                                        )}
                                    </td>

                                    <td>
                                        $
                                        {formatMoney(
                                            position.market_value_usd
                                        )}
                                    </td>

                                    <td
                                        className={
                                            Number(
                                                position.unrealized_pnl_usd
                                            ) >= 0
                                                ? "value-positive"
                                                : "value-negative"
                                        }
                                    >
                                        $
                                        {formatMoney(
                                            position.unrealized_pnl_usd
                                        )}
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

export default OpenPositions;
