import api from "./client";

export const getLabBacktest = async () => (await api.get("/api/lab/backtest")).data;

export const getLabLive = async () => (await api.get("/api/lab/live")).data;

export const getLabTrades = async (limit = 30, symbol) =>
    (await api.get("/api/lab/trades", { params: { limit, symbol } })).data;

export const getCandles = async (symbol, tf, limit = 300) =>
    (await api.get("/api/lab/candles", { params: { symbol, tf, limit } })).data;

export const getBrain = async () => (await api.get("/api/lab/brain")).data;

export const getTelegram = async () => (await api.get("/api/lab/telegram")).data;
