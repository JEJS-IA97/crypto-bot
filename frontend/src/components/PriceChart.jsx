import { formatMoney } from "../utils/format";

const WIDTH = 280;
const HEIGHT = 120;
const PAD = 8;

/* Gráfica de precio en vivo del par principal: usa el mismo
   historial de ticks que las sparklines (sin tocar la API). */
function PriceChart({ points, symbol = "BTCUSDT" }) {
    if (!Array.isArray(points) || points.length < 2) {
        return (
            <div className="price-chart" data-testid="price-chart-empty">
                <span className="price-chart-title">
                    Precio {symbol.replace(/USDT$/, "")}
                </span>

                <p className="price-chart-note">
                    Esperando ticks de mercado…
                </p>
            </div>
        );
    }

    const values = points.map((value) => Number(value)).filter(Number.isFinite);

    if (values.length < 2) {
        return (
            <div className="price-chart" data-testid="price-chart-empty">
                <span className="price-chart-title">
                    Precio {symbol.replace(/USDT$/, "")}
                </span>

                <p className="price-chart-note">
                    Esperando ticks de mercado…
                </p>
            </div>
        );
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const innerWidth = WIDTH - PAD * 2;
    const innerHeight = HEIGHT - PAD * 2;
    const step = innerWidth / (values.length - 1);
    const x = (index) => PAD + index * step;
    const y = (value) => PAD + ((max - value) / span) * innerHeight;

    const linePoints = values
        .map((value, index) => `${x(index)},${y(value)}`)
        .join(" ");
    const areaPoints = `${linePoints} ${x(values.length - 1)},${HEIGHT - PAD} ${PAD},${HEIGHT - PAD}`;

    const rising = values[values.length - 1] >= values[0];
    const changePct = ((values[values.length - 1] - values[0]) / values[0]) * 100;

    return (
        <div className="price-chart" data-testid="price-chart">
            <span className="price-chart-title">
                Precio {symbol.replace(/USDT$/, "")}
            </span>

            <svg
                className={`price-chart-svg ${rising ? "price-chart-up" : "price-chart-down"}`}
                viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                role="img"
                aria-label={`Gráfica de precio de ${symbol}`}
            >
                <polygon className="price-chart-area" points={areaPoints} />
                <polyline className="price-chart-line" points={linePoints} />
            </svg>

            <p className={`price-chart-note ${rising ? "value-positive" : "value-negative"}`}>
                ${formatMoney(values[values.length - 1])}{" "}
                ({rising ? "▲" : "▼"} {Math.abs(changePct).toFixed(2)}%)
            </p>
        </div>
    );
}

export default PriceChart;
