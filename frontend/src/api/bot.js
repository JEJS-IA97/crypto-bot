import api from "./client";

export const getBotStatus = async () => {
    const response = await api.get("/api/bot/status");
    return response.data;
};

export const getBotMetrics = async () => {
    const response = await api.get("/api/bot/metrics");
    return response.data;
};

export const getDecisions = async (params = {}) => {
    const response = await api.get("/api/signals/decisions", {
        params,
    });
    return response.data;
};

export const startBot = async () => {
    const response = await api.post("/api/bot/start");
    return response.data;
};

export const stopBot = async () => {
    const response = await api.post("/api/bot/stop");
    return response.data;
};
