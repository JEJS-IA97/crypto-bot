import { useCallback, useEffect, useRef, useState } from "react";

import {
    createAccount,
    getAccounts,
    getBalance,
    getMarketPrices,
    getPositions,
    getSummary,
    getTrades,
} from "../api/simulation";

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

const PRICE_REFRESH_MS = 1000;
const SUMMARY_REFRESH_MS = 5000;
// Ventana de la sparkline/curva de precio en memoria (2 min a 1 tick/s).
const PRICE_HISTORY_LIMIT = 120;

export default function useSimulationData() {
    const [account, setAccount] = useState(null);
    const [summary, setSummary] = useState(null);
    const [balance, setBalance] = useState(null);
    const [positions, setPositions] = useState([]);
    const [trades, setTrades] = useState([]);
    const [marketPrices, setMarketPrices] = useState([]);
    const [priceHistory, setPriceHistory] = useState({});
    const historyRef = useRef({});

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const loadMarketPrices = useCallback(async () => {
        const data = await getMarketPrices();

        const list = normalizeArray(data, [
            "prices",
            "market_prices",
            "data",
            "items",
        ]);

        setMarketPrices(list);

        const history = { ...historyRef.current };

        for (const item of list) {
            const price = Number(item?.price_usd);

            if (!item?.symbol || !Number.isFinite(price)) {
                continue;
            }

            const points = history[item.symbol] || [];

            history[item.symbol] = points
                .concat(price)
                .slice(-PRICE_HISTORY_LIMIT);
        }

        historyRef.current = history;
        setPriceHistory(history);
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
            balanceData &&
                typeof balanceData === "object" &&
                !Array.isArray(balanceData)
                ? balanceData
                : null
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
        // loadSimulation() es async: el primer setState ocurre dentro de
        // la cadena asíncrona, no de forma síncrona en el effect
        // (falso positivo de la regla, igual que en MetricsPanel).
        // eslint-disable-next-line react-hooks/set-state-in-effect
        loadSimulation();
    }, [loadSimulation]);

    useEffect(() => {
        // Precios por segundo: el backend cachea 2 s, así que cada tick
        // trae cambio real en lugar de la tabla congelada.
        const timer = setInterval(() => {
            loadMarketPrices().catch(() => {
                // red caída: el siguiente tick reintenta
            });
        }, PRICE_REFRESH_MS);

        return () => clearInterval(timer);
    }, [loadMarketPrices]);

    const reload = useCallback(async () => {
        if (!account) {
            return;
        }

        await loadAccountData(account.id);
    }, [account, loadAccountData]);

    useEffect(() => {
        if (!account) {
            return undefined;
        }

        // Equity/posiciones: mark-to-market con los precios vivos.
        const timer = setInterval(() => {
            reload().catch(() => {
                // red caída: el siguiente tick reintenta
            });
        }, SUMMARY_REFRESH_MS);

        return () => clearInterval(timer);
    }, [account, reload]);

    return {
        account,
        summary,
        balance,
        positions,
        trades,
        marketPrices,
        priceHistory,
        loading,
        error,
        reload,
    };
}
