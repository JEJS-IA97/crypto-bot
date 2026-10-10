import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", async () => {
    const { default: api } = await vi.importActual("../client");
    const calls = [];
    api.defaults.adapter = async (config) => {
        calls.push(config);
        return {
            data: {},
            status: config.method === "post" ? 201 : 200,
            statusText: "OK",
            headers: {},
            config,
        };
    };
    return { default: api, calls };
});

async function importLearning() {
    const client = await import("../client");
    const learning = await import("../learning");
    return { ...learning, calls: client.calls };
}

describe("api learning (RF-4)", () => {
    beforeEach(async () => {
        vi.clearAllMocks();
        localStorage.clear();
        const client = await import("../client");
        client.calls.length = 0;
    });

    it("getHypotheses hace GET /api/learning/hypotheses", async () => {
        const { getHypotheses, calls } = await importLearning();
        await getHypotheses();

        expect(calls).toHaveLength(1);
        expect(calls[0].method).toBe("get");
        expect(calls[0].url).toBe("/api/learning/hypotheses");
    });

    it("createHypothesis hace POST con el statement", async () => {
        const { createHypothesis, calls } = await importLearning();
        await createHypothesis({ statement: "funding extremo" });

        expect(calls[0].method).toBe("post");
        expect(calls[0].url).toBe("/api/learning/hypotheses");
        expect(JSON.parse(calls[0].data)).toEqual({
            statement: "funding extremo",
        });
    });

    it("transitionHypothesis hace POST a /{id}/transition con to y reason", async () => {
        const { transitionHypothesis, calls } = await importLearning();
        await transitionHypothesis(7, {
            to: "ACTIVE",
            reason: "umbral superado",
        });

        expect(calls[0].method).toBe("post");
        expect(calls[0].url).toBe(
            "/api/learning/hypotheses/7/transition"
        );
        expect(JSON.parse(calls[0].data)).toEqual({
            to: "ACTIVE",
            reason: "umbral superado",
        });
    });

    it("evaluateHypothesis hace POST a /{id}/evaluate", async () => {
        const { evaluateHypothesis, calls } = await importLearning();
        await evaluateHypothesis(3);

        expect(calls[0].method).toBe("post");
        expect(calls[0].url).toBe(
            "/api/learning/hypotheses/3/evaluate"
        );
    });

    it("getKnowledge hace GET /api/learning/knowledge", async () => {
        const { getKnowledge, calls } = await importLearning();
        await getKnowledge();

        expect(calls[0].method).toBe("get");
        expect(calls[0].url).toBe("/api/learning/knowledge");
    });

    it("getStrategyVersions hace GET /api/learning/strategy-versions", async () => {
        const { getStrategyVersions, calls } =
            await importLearning();
        await getStrategyVersions();

        expect(calls[0].method).toBe("get");
        expect(calls[0].url).toBe(
            "/api/learning/strategy-versions"
        );
    });

    it("envía el token Bearer en las llamadas de learning", async () => {
        const { getHypotheses, calls } = await importLearning();
        localStorage.setItem("crypto_bot_api_token", "sekret");
        await getHypotheses();

        expect(calls[0].headers.Authorization).toBe(
            "Bearer sekret"
        );
    });
});
