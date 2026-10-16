import api from "./client";

export const getLabBacktest = async () => (await api.get("/api/lab/backtest")).data;

export const getLabLive = async () => (await api.get("/api/lab/live")).data;

export const getLabTrades = async (limit = 30) =>
    (await api.get("/api/lab/trades", { params: { limit } })).data;
