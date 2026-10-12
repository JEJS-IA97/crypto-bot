import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import useSimulationData from "../useSimulationData";
import {
    getAccounts,
    getBalance,
    getMarketPrices,
    getPositions,
    getSummary,
    getTrades,
} from "../../api/simulation";

vi.mock("../../api/simulation", () => ({
    createAccount: vi.fn(),
    getAccounts: vi.fn(),
    getBalance: vi.fn(),
    getMarketPrices: vi.fn(),
    getPositions: vi.fn(),
    getSummary: vi.fn(),
    getTrades: vi.fn(),
    createOrder: vi.fn(),
    resetAccount: vi.fn(),
}));

const ACCOUNT = { id: 1, name: "prod" };

async function flush() {
    await act(async () => {});
}

describe("useSimulationData: precios en vivo", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        getAccounts.mockResolvedValue([ACCOUNT]);
        getSummary.mockResolvedValue({ account_id: 1 });
        getBalance.mockResolvedValue({ available_usd: "40.00" });
        getPositions.mockResolvedValue([]);
        getTrades.mockResolvedValue([]);
        getMarketPrices.mockResolvedValue([]);
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it("refresca los precios cada segundo", async () => {
        const { unmount } = renderHook(() => useSimulationData());
        await flush();

        expect(getMarketPrices).toHaveBeenCalledTimes(1);

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1000);
        });

        expect(getMarketPrices).toHaveBeenCalledTimes(2);

        unmount();

        await act(async () => {
            await vi.advanceTimersByTimeAsync(3000);
        });

        expect(getMarketPrices).toHaveBeenCalledTimes(2);
    });
});
