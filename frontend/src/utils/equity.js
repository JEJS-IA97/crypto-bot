function isPresent(value) {
    return value !== null && value !== undefined && value !== "";
}

export function buildEquitySeries(trades, { availableBalance, currentTotal } = {}) {
    if (!isPresent(availableBalance)) {
        return [];
    }

    const sorted = [...(trades || [])].sort(
        (a, b) => new Date(a.executed_at) - new Date(b.executed_at)
    );

    let deltaSum = 0;
    for (const trade of sorted) {
        const total = Number(trade.total_usd || 0);
        const fee = Number(trade.fee_usd || 0);
        deltaSum += trade.side === "BUY" ? -(total + fee) : total - fee;
    }

    const initial = Number(availableBalance) - deltaSum;
    const points = [{ label: "Inicio", value: initial }];

    let cumulative = initial;
    for (const trade of sorted) {
        const fee = Number(trade.fee_usd || 0);
        const realized = Number(trade.realized_pnl_usd || 0);
        cumulative += trade.side === "BUY" ? -fee : realized;
        points.push({
            label: new Date(trade.executed_at).toISOString(),
            value: cumulative,
        });
    }

    if (isPresent(currentTotal)) {
        points.push({ label: "Actual", value: Number(currentTotal) });
    }

    return points;
}
