import api from "./client";

export const getPipeline = async () => {
    const response = await api.get("/api/bot/pipeline");
    return response.data;
};

export const getEvents = async (params = {}) => {
    const response = await api.get("/api/bot/events", { params });
    return response.data;
};

export const getSources = async () => {
    const response = await api.get("/api/bot/sources");
    return response.data;
};

export const getObservability = async () => {
    const response = await api.get("/api/bot/observability");
    return response.data;
};
