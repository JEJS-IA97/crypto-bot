const NO_CORRELATION = "sin-correlacion";

export const EVENT_LABELS = {
    "decision.emitted": "Decisión emitida",
    "decision.blocked": "Decisión bloqueada",
    "risk.evaluated": "Evaluación de riesgo",
    "ai.consultation": "Consulta IA",
    "order.sent": "Orden enviada",
    "order.filled": "Orden ejecutada",
    "order.failed": "Orden fallida",
    "cycle.completed": "Ciclo completado",
};

function newestFirst(left, right) {
    const leftStamp = String(left.created_at);
    const rightStamp = String(right.created_at);
    if (leftStamp === rightStamp) {
        return 0;
    }
    return leftStamp > rightStamp ? -1 : 1;
}

function oldestFirst(left, right) {
    const leftStamp = String(left.created_at);
    const rightStamp = String(right.created_at);
    if (leftStamp === rightStamp) {
        return Number(left.id) - Number(right.id);
    }
    return leftStamp < rightStamp ? -1 : 1;
}

export function groupByCorrelation(events = []) {
    const buckets = new Map();

    for (const event of events) {
        const key = event.correlation_id || NO_CORRELATION;
        if (!buckets.has(key)) {
            buckets.set(key, []);
        }
        buckets.get(key).push(event);
    }

    const groups = [];
    for (const [key, rows] of buckets) {
        groups.push({
            correlationId: key === NO_CORRELATION ? null : key,
            events: [...rows].sort(oldestFirst),
        });
    }

    return groups.sort((left, right) =>
        newestFirst(left.events[left.events.length - 1], right.events[right.events.length - 1])
    );
}
