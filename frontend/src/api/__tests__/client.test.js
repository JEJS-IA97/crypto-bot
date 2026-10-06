import { beforeEach, describe, expect, it, vi } from "vitest";

async function importClient() {
    return import("../client");
}

describe("client API", () => {
    beforeEach(() => {
        vi.resetModules();
        localStorage.clear();
    });

    it("usa VITE_API_URL cuando está definida", async () => {
        vi.stubEnv("VITE_API_URL", "https://crypto-bot.onrender.com");
        const { default: api } = await importClient();
        expect(api.defaults.baseURL).toBe(
            "https://crypto-bot.onrender.com"
        );
        vi.unstubAllEnvs();
    });

    it("usa localhost como fallback sin VITE_API_URL", async () => {
        const { default: api } = await importClient();
        expect(api.defaults.baseURL).toBe("http://127.0.0.1:8000");
    });

    it("añade Authorization Bearer cuando hay token guardado", async () => {
        const { default: api, setToken } = await importClient();
        const requests = [];
        api.defaults.adapter = async (config) => {
            requests.push(config);
            return {
                data: {},
                status: 200,
                statusText: "OK",
                headers: {},
                config,
            };
        };

        setToken("secreto-123");
        await api.get("/health");

        expect(requests).toHaveLength(1);
        expect(requests[0].headers.Authorization).toBe(
            "Bearer secreto-123"
        );
    });

    it("no envía Authorization sin token", async () => {
        const { default: api } = await importClient();
        const requests = [];
        api.defaults.adapter = async (config) => {
            requests.push(config);
            return {
                data: {},
                status: 200,
                statusText: "OK",
                headers: {},
                config,
            };
        };

        await api.get("/health");

        expect(requests[0].headers.Authorization).toBeUndefined();
    });

    it("setToken guarda en localStorage y clearToken lo elimina", async () => {
        const { setToken, getToken, clearToken } = await importClient();

        setToken("abc");
        expect(getToken()).toBe("abc");
        expect(
            localStorage.getItem("crypto_bot_api_token")
        ).toBe("abc");

        clearToken();
        expect(getToken()).toBe("");
        expect(
            localStorage.getItem("crypto_bot_api_token")
        ).toBeNull();
    });
});
