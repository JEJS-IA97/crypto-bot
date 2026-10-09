import { describe, expect, it } from "vitest";

import { groupByCorrelation } from "../events";

const EVENTS = [
    {
        id: 3,
        correlation_id: "corr-a",
        created_at: "2026-10-07T12:00:03Z",
        event: "order.filled",
    },
    {
        id: 1,
        correlation_id: "corr-a",
        created_at: "2026-10-07T12:00:01Z",
        event: "decision.emitted",
    },
    {
        id: 2,
        correlation_id: "corr-a",
        created_at: "2026-10-07T12:00:02Z",
        event: "risk.evaluated",
    },
    {
        id: 4,
        correlation_id: null,
        created_at: "2026-10-07T13:00:00Z",
        event: "cycle.completed",
    },
];

describe("groupByCorrelation", () => {
    it("agrupa por correlation_id y ordena cada grupo ascendente", () => {
        const groups = groupByCorrelation(EVENTS);
        const group = groups.find((item) => item.correlationId === "corr-a");
        expect(group).toBeDefined();
        expect(group.events.map((event) => event.event)).toEqual([
            "decision.emitted",
            "risk.evaluated",
            "order.filled",
        ]);
    });

    it("ordena los grupos por el evento más reciente y agrupa los sin correlación", () => {
        const groups = groupByCorrelation(EVENTS);
        expect(groups).toHaveLength(2);
        expect(groups[0].correlationId).toBeNull();
    });

    it("lista vacía devuelve []", () => {
        expect(groupByCorrelation([])).toEqual([]);
    });
});
