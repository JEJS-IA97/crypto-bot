import api from "./client";

export const getAccounts = async () => {
    const response = await api.get("/simulation/accounts");
    return response.data;
};

export const getSummary = async (accountId) => {
    const response = await api.get(
        `/simulation/accounts/${accountId}/summary`
    );

    return response.data;
};

export const getBalance = async (accountId) => {
    const response = await api.get(
        `/simulation/accounts/${accountId}/balance`
    );

    return response.data;
};

export const getPositions = async (accountId) => {
    const response = await api.get(
        `/simulation/accounts/${accountId}/positions`
    );

    return response.data;
};

export const getTrades = async (accountId) => {
    const response = await api.get(
        `/simulation/accounts/${accountId}/trades`
    );

    return response.data;
};

export const createAccount = async (account) => {
    const response = await api.post(
        "/simulation/accounts",
        account
    );

    return response.data;
};

export const createOrder = async (accountId, order) => {
    const response = await api.post(
        `/simulation/accounts/${accountId}/orders`,
        order
    );

    return response.data;
};

export const resetAccount = async (accountId) => {
    const response = await api.post(
        `/simulation/accounts/${accountId}/reset`
    );

    return response.data;
};

export const getMarketPrices = async () => {
    const response = await api.get(
        "/simulation/market-prices"
    );

    return response.data;
};

export const updateMarketPrice = async (marketPrice) => {
    const response = await api.put(
        "/simulation/market-prices",
        marketPrice
    );

    return response.data;
};