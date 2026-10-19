const usd = new Intl.NumberFormat("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const money = (v) => (v === null || v === undefined ? "—" : usd.format(Number(v)));

export const signed = (v, suffix = "") =>
    v === null || v === undefined ? "—" : `${Number(v) > 0 ? "+" : ""}${usd.format(Number(v))}${suffix}`;

export const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");

export function price(v) {
    if (v === null || v === undefined) return "—";
    const n = Number(v);
    const digits = n >= 1000 ? 2 : n >= 1 ? 3 : 5;
    return n.toLocaleString("es-VE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function clock(ms) {
    if (!ms) return "—";
    return new Date(ms).toLocaleString("es-VE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}

export const coin = (symbol) => symbol.replace("USDT", "");
