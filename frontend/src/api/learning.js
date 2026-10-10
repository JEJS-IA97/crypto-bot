import api from "./client";

export const getHypotheses = async () => {
    const response = await api.get("/api/learning/hypotheses");
    return response.data;
};

export const createHypothesis = async (payload) => {
    const response = await api.post(
        "/api/learning/hypotheses",
        payload
    );
    return response.data;
};

export const transitionHypothesis = async (id, payload) => {
    const response = await api.post(
        `/api/learning/hypotheses/${id}/transition`,
        payload
    );
    return response.data;
};

export const evaluateHypothesis = async (id) => {
    const response = await api.post(
        `/api/learning/hypotheses/${id}/evaluate`
    );
    return response.data;
};

export const getKnowledge = async () => {
    const response = await api.get("/api/learning/knowledge");
    return response.data;
};

export const getStrategyVersions = async () => {
    const response = await api.get(
        "/api/learning/strategy-versions"
    );
    return response.data;
};
