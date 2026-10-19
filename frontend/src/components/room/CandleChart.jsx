import { useEffect, useRef, useState } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";

import { getCandles, getLabTrades } from "../../api/lab";
import { coin, price, signed, tone } from "./fmt";

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"];
const TFS = [
    ["15m", 900],
    ["1h", 3600],
    ["4h", 14400],
    ["1d", 86400],
];
const C = {
    bg: "#14171b",
    text: "#8b939d",
    grid: "#1d2126",
    up: "#26a96c",
    down: "#e5534b",
    sma50: "#f0b429",
    sma200: "#7c8ea6",
};

function sma(candles, n) {
    const out = [];
    let sum = 0;
    candles.forEach((c, i) => {
        sum += c.close;
        if (i >= n) sum -= candles[i - n].close;
        if (i >= n - 1) out.push({ time: c.time, value: sum / n });
    });
    return out;
}

/** Entradas y salidas del torneo, ajustadas a la vela que las contiene. */
function markers(trades, candles, step) {
    if (!candles.length) return [];
    const first = candles[0].time;
    const snap = (ms) => Math.floor(ms / 1000 / step) * step;
    const out = [];
    for (const t of trades) {
        const open = snap(t.opened_ts);
        if (open >= first) {
            out.push({
                time: open,
                position: t.side === "LONG" ? "belowBar" : "aboveBar",
                color: t.side === "LONG" ? C.up : C.down,
                shape: t.side === "LONG" ? "arrowUp" : "arrowDown",
                text: "",
            });
        }
        if (t.closed_ts && snap(t.closed_ts) >= first) {
            out.push({
                time: snap(t.closed_ts),
                position: "aboveBar",
                color: t.pnl > 0 ? C.up : C.down,
                shape: "circle",
                text: "",
            });
        }
    }
    return out.sort((a, b) => a.time - b.time);
}

function CandleChart() {
    const box = useRef(null);
    const series = useRef(null);
    const [symbol, setSymbol] = useState("BTCUSDT");
    const [tf, setTf] = useState("1h");
    const [info, setInfo] = useState({ last: null, change: null, count: 0, trades: 0 });
    const [error, setError] = useState("");

    useEffect(() => {
        const chart = createChart(box.current, {
            autoSize: true,
            layout: { background: { color: C.bg }, textColor: C.text, fontFamily: "IBM Plex Sans, sans-serif", fontSize: 12 },
            grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
            crosshair: { mode: CrosshairMode.Normal },
            rightPriceScale: { borderColor: "#262b31" },
            timeScale: { borderColor: "#262b31", timeVisible: true, secondsVisible: false },
            localization: { locale: "es-VE" },
        });
        const candles = chart.addCandlestickSeries({
            upColor: C.up,
            downColor: C.down,
            wickUpColor: C.up,
            wickDownColor: C.down,
            borderVisible: false,
        });
        const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
        chart.priceScale("").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        const s50 = chart.addLineSeries({ color: C.sma50, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        const s200 = chart.addLineSeries({ color: C.sma200, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        series.current = { chart, candles, volume, s50, s200 };
        return () => chart.remove();
    }, []);

    useEffect(() => {
        let alive = true;
        const step = TFS.find(([k]) => k === tf)[1];
        const load = async (fit) => {
            try {
                const [data, trades] = await Promise.all([getCandles(symbol, tf, 500), getLabTrades(300, symbol)]);
                if (!alive || !series.current) return;
                const rows = data.candles;
                const s = series.current;
                s.candles.setData(rows);
                s.volume.setData(rows.map((c) => ({ time: c.time, value: c.volume, color: c.close >= c.open ? "#26a96c26" : "#e5534b26" })));
                s.s50.setData(sma(rows, 50));
                s.s200.setData(sma(rows, 200));
                s.candles.setMarkers(markers(trades, rows, step));
                if (fit) s.chart.timeScale().fitContent();
                const last = data.price ?? rows.at(-1)?.close ?? null;
                const dayAgo = rows.find((c) => c.time >= (rows.at(-1)?.time ?? 0) - 86400);
                setInfo({
                    last,
                    change: dayAgo && last ? ((last - dayAgo.open) / dayAgo.open) * 100 : null,
                    count: rows.length,
                    trades: trades.length,
                });
                setError(rows.length ? "" : "El torneo aún no tiene velas de este par (¿está encendido LAB_ENABLED?)");
            } catch {
                if (alive) setError("No pude leer las velas del bot.");
            }
        };
        load(true);
        const timer = setInterval(() => load(false), 15000);
        return () => {
            alive = false;
            clearInterval(timer);
        };
    }, [symbol, tf]);

    return (
        <section className="panel chart-panel" aria-label="Gráfico de velas">
            <header className="chart-head">
                <div className="seg" role="tablist" aria-label="Par">
                    {SYMBOLS.map((s) => (
                        <button key={s} role="tab" aria-selected={s === symbol} className={s === symbol ? "on" : ""} onClick={() => setSymbol(s)}>
                            {coin(s)}
                        </button>
                    ))}
                </div>
                <div className="quote">
                    <span className="num big">{price(info.last)}</span>
                    <span className={`num ${tone(info.change)}`}>{signed(info.change, " %")} 24 h</span>
                </div>
                <div className="legend">
                    <span><i style={{ background: C.sma50 }} />SMA50</span>
                    <span><i style={{ background: C.sma200 }} />SMA200</span>
                    <span className="dim">▲▼ entradas · ● salidas ({info.trades})</span>
                </div>
                <div className="seg" role="tablist" aria-label="Temporalidad">
                    {TFS.map(([k]) => (
                        <button key={k} role="tab" aria-selected={k === tf} className={k === tf ? "on" : ""} onClick={() => setTf(k)}>
                            {k}
                        </button>
                    ))}
                </div>
            </header>
            <div className="chart-box" ref={box} />
            {error && <p className="note">{error}</p>}
        </section>
    );
}

export default CandleChart;
