import { useCallback, useEffect, useState } from "react";

import {
    createAccount,
    getAccounts,
    getBalance,
    getMarketPrices,
    getPositions,
    getSummary,
    getTrades,
} from "../api/simulation";

import TradingPanel from "../components/TradingPanel";
import MarketPanel from "../components/MarketPanel";

function formatMoney(value) {
    return Number(value || 0).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 8,
    });
}

function normalizeArray(data, propertyNames = []) {
    if (Array.isArray(data)) {
        return data;
    }

    if (!data || typeof data !== "object") {
        return [];
    }

    for (const propertyName of propertyNames) {
        if (Array.isArray(data[propertyName])) {
            return data[propertyName];
        }
    }

    return [];
}

function Simulation() {
    const [accounts, setAccounts] = useState([]);
    const [account, setAccount] = useState(null);
    const [summary, setSummary] = useState(null);
    const [balance, setBalance] = useState([]);
    const [positions, setPositions] = useState([]);
    const [trades, setTrades] = useState([]);
    const [marketPrices, setMarketPrices] = useState([]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const loadMarketPrices = useCallback(async () => {
        const data = await getMarketPrices();

        setMarketPrices(
            normalizeArray(data, [
                "prices",
                "market_prices",
                "data",
                "items",
            ])
        );
    }, []);

    const loadAccountData = useCallback(async (accountId) => {
        const [
            summaryData,
            balanceData,
            positionsData,
            tradesData,
        ] = await Promise.all([
            getSummary(accountId),
            getBalance(accountId),
            getPositions(accountId),
            getTrades(accountId),
        ]);

        setSummary(summaryData);

        setBalance(
            normalizeArray(balanceData, [
                "balances",
                "balance",
                "data",
                "items",
            ])
        );

        setPositions(
            normalizeArray(positionsData, [
                "positions",
                "data",
                "items",
            ])
        );

        setTrades(
            normalizeArray(tradesData, [
                "trades",
                "transactions",
                "data",
                "items",
            ])
        );
    }, []);

    const loadSimulation = useCallback(async () => {
        try {
            setLoading(true);
            setError("");

            let accountList = await getAccounts();

            accountList = normalizeArray(accountList, [
                "accounts",
                "data",
                "items",
            ]);

            if (accountList.length === 0) {
                await createAccount({
                    name: "Default Simulation",
                    initial_balance_usd: "20.00",
                });

                accountList = await getAccounts();

                accountList = normalizeArray(accountList, [
                    "accounts",
                    "data",
                    "items",
                ]);
            }

            if (accountList.length === 0) {
                throw new Error(
                    "No se pudo crear o recuperar la cuenta de simulación."
                );
            }

            const selectedAccount = accountList[0];

            setAccounts(accountList);
            setAccount(selectedAccount);

            await Promise.all([
                loadAccountData(selectedAccount.id),
                loadMarketPrices(),
            ]);
        } catch (requestError) {
            console.error(
                "Error cargando la simulación:",
                requestError
            );

            const detail = requestError.response?.data?.detail;

            setError(
                detail ||
                    requestError.message ||
                    "No se pudo cargar la simulación."
            );
        } finally {
            setLoading(false);
        }
    }, [loadAccountData, loadMarketPrices]);

    useEffect(() => {
        loadSimulation();
    }, [loadSimulation]);

    const handleOrderExecuted = async () => {
        if (!account) {
            return;
        }

        await loadAccountData(account.id);
    };

    const handleMarketPriceUpdated = async () => {
        await loadMarketPrices();

        if (account) {
            await loadAccountData(account.id);
        }
    };

    if (loading) {
        return (
            <main className="simulation-page">
                <div className="loading-state">
                    Cargando simulación...
                </div>
            </main>
        );
    }

    if (error) {
        return (
            <main className="simulation-page">
                <div className="form-message error">
                    {error}
                </div>
            </main>
        );
    }

    if (!account || !summary) {
        return (
            <main className="simulation-page">
                <div className="empty-state">
                    No hay una cuenta de simulación disponible.
                </div>
            </main>
        );
    }

    const accountBalance = summary.balance || {};

    const availableBalance = accountBalance.available_usd || 0;
    const totalBalance = accountBalance.total_balance_usd || 0;
    const investedBalance = accountBalance.invested_usd || 0;
    const realizedPnl = accountBalance.realized_pnl_usd || 0;
    const unrealizedPnl = accountBalance.unrealized_pnl_usd || 0;

    return (
        <main className="simulation-page">
            <div className="page-header">
                <div className="page-heading">
                    <span className="eyebrow">
                        PAPER TRADING
                    </span>

                    <h1>Simulación</h1>

                    <p>
                        Opera con dinero ficticio sin afectar fondos
                        reales.
                    </p>
                </div>

                <div className="simulation-badge">
                    <span className="status-dot" />
                    SIMULACIÓN ACTIVA
                </div>
            </div>

            <section className="account-summary">
                <div className="account-info">
                    <span className="eyebrow">
                        CUENTA ACTIVA
                    </span>

                    <h2>{account.name}</h2>

                    <span className="account-id">
                        ID: {account.id}
                    </span>
                </div>

                <div className="summary-grid">
                    <article className="summary-card summary-blue">
                        <span>Balance total</span>

                        <strong>
                            ${formatMoney(totalBalance)}
                        </strong>

                        <small>
                            Valor actual de la cuenta
                        </small>
                    </article>

                    <article className="summary-card summary-green">
                        <span>Disponible</span>

                        <strong>
                            ${formatMoney(availableBalance)}
                        </strong>

                        <small>
                            Capital disponible para operar
                        </small>
                    </article>

                    <article className="summary-card summary-purple">
                        <span>Invertido</span>

                        <strong>
                            ${formatMoney(investedBalance)}
                        </strong>

                        <small>
                            Coste de posiciones abiertas
                        </small>
                    </article>

                    <article className="summary-card summary-cyan">
                        <span>PnL realizado</span>

                        <strong
                            className={
                                Number(realizedPnl) >= 0
                                    ? "value-positive"
                                    : "value-negative"
                            }
                        >
                            ${formatMoney(realizedPnl)}
                        </strong>

                        <small>
                            Resultado de operaciones cerradas
                        </small>
                    </article>

                    <article className="summary-card summary-orange">
                        <span>PnL no realizado</span>

                        <strong
                            className={
                                Number(unrealizedPnl) >= 0
                                    ? "value-positive"
                                    : "value-negative"
                            }
                        >
                            ${formatMoney(unrealizedPnl)}
                        </strong>

                        <small>
                            Resultado de posiciones abiertas
                        </small>
                    </article>
                </div>
            </section>

            <section className="top-panels-grid">
                <TradingPanel
                    accountId={account.id}
                    marketPrices={marketPrices}
                    positions={positions}
                    availableBalance={availableBalance}
                    onOrderExecuted={handleOrderExecuted}
                />

                <MarketPanel
                    marketPrices={marketPrices}
                    onMarketPriceUpdated={handleMarketPriceUpdated}
                />
            </section>

            <section className="bottom-panels-grid">
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
                            <span className="empty-state-icon">▣</span>
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

                <section className="data-section">
                    <div className="section-header">
                        <div>
                            <span className="eyebrow">
                                ACCOUNT BALANCE
                            </span>

                            <h2>Balances</h2>
                        </div>
                    </div>

                    {balance.length === 0 ? (
                        <div className="empty-state table-empty-state">
                            <span className="empty-state-icon">▣</span>
                            <span>
                                No hay balances registrados.
                            </span>
                        </div>
                    ) : (
                        <div className="data-table-wrapper">
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Activo</th>
                                        <th>Disponible</th>
                                        <th>Bloqueado</th>
                                        <th>Valor estimado</th>
                                    </tr>
                                </thead>

                                <tbody>
                                    {balance.map((item) => (
                                        <tr key={item.asset}>
                                            <td>
                                                <strong>
                                                    {item.asset}
                                                </strong>
                                            </td>

                                            <td>
                                                {item.free}
                                            </td>

                                            <td>
                                                {item.locked}
                                            </td>

                                            <td>
                                                $
                                                {formatMoney(
                                                    item.value_usd
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>

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
                            <span className="empty-state-icon">▤</span>
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
                                                {new Date(
                                                    trade.executed_at
                                                ).toLocaleString()}
                                            </td>

                                            <td>
                                                <strong>
                                                    {trade.symbol}
                                                </strong>
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

                                            <td>
                                                {trade.quantity}
                                            </td>

                                            <td>
                                                $
                                                {formatMoney(
                                                    trade.price
                                                )}
                                            </td>

                                            <td>
                                                $
                                                {formatMoney(
                                                    trade.total_usd
                                                )}
                                            </td>

                                            <td>
                                                $
                                                {formatMoney(
                                                    trade.fee_usd
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>
            </section>
        </main>
    );
}

export default Simulation;