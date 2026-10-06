import api from "./client";

export const sendExternalSignal = async (signal) => {
    const response = await api.post("/api/signals/external", signal);
    return response.data;
};
