import { buildEquitySeries } from "../utils/equity";
import { formatMoney } from "../utils/format";

const WIDTH = 720;
const HEIGHT = 220;
const PAD_LEFT = 64;
const PAD_RIGHT = 20;
const PAD_TOP = 16;
const PAD_BOTTOM = 30;

function buildGeometry(series) {
    const values = series.map((point) => point.value);
    let min = Math.min(...values);
    let max = Math.max(...values);

    if (min === max) {
        min -= 1;
        max += 1;
    }

    const innerWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
    const innerHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
    const stepX =
        series.length > 1 ? innerWidth / (series.length - 1) : 0;

    const x = (index) => PAD_LEFT + index * stepX;
    const y = (value) => PAD_TOP + ((max - value) / (max - min)) * innerHeight;

    return { min, max, innerHeight, x, y };
}

function EquityChart({
    trades = [],
    availableBalance,
    currentTotal,
    loading = false,
    error = "",
    onSelectDecision = null,
}) {
    if (loading) {
        return (
            <div className="equity-chart">
                <div className="equity-empty" data-testid="equity-loading">
                    Cargando curva de equity…
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="equity-chart">
                <div className="equity-empty" data-testid="equity-error">
                    {error}
                </div>
            </div>
        );
    }

    const series = buildEquitySeries(trades, {
        availableBalance,
        currentTotal,
    });

    if (series.length < 2) {
        return (
            <div className="equity-chart">
                <div className="equity-empty" data-testid="equity-empty">
                    Sin datos de equity todavía.
                </div>
            </div>
        );
    }

    const { min, max, innerHeight, x, y } = buildGeometry(series);
    const linePoints = series
        .map((point, index) => `${x(index)},${y(point.value)}`)
        .join(" ");

    const areaPoints = `${linePoints} ${x(series.length - 1)},${PAD_TOP + innerHeight} ${x(0)},${PAD_TOP + innerHeight}`;

    const gridRows = [0, 0.5, 1];
    const lastPoint = series[series.length - 1];

    // RF-7: un marcador por cada operación cerrada enlazada a una
    // decisión (misma posición que su punto en la serie).
    const sortedTrades = [...trades].sort(
        (left, right) =>
            new Date(left.executed_at) - new Date(right.executed_at)
    );
    const markers = sortedTrades
        .map((trade, index) => ({
            trade,
            seriesIndex: index + 1,
        }))
        .filter(
            ({ trade }) =>
                trade.decision_id !== null &&
                trade.decision_id !== undefined
        );

    return (
        <div className="equity-chart">
            <svg
                className="equity-svg"
                viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                role="img"
                aria-label="Curva de equity de la cuenta"
            >
                {gridRows.map((fraction) => (
                    <g key={fraction}>
                        <line
                            className="equity-grid-line"
                            x1={PAD_LEFT}
                            y1={PAD_TOP + fraction * innerHeight}
                            x2={WIDTH - PAD_RIGHT}
                            y2={PAD_TOP + fraction * innerHeight}
                        />
                        <text
                            className="equity-axis-label"
                            x={PAD_LEFT - 8}
                            y={PAD_TOP + fraction * innerHeight + 4}
                            textAnchor="end"
                        >
                            {formatMoney(max - fraction * (max - min))}
                        </text>
                    </g>
                ))}

                <polygon className="equity-area" points={areaPoints} />
                <polyline
                    className="equity-line"
                    points={linePoints}
                />

                {series.map((point, index) => (
                    <circle
                        key={`${point.label}-${index}`}
                        className={
                            index === series.length - 1
                                ? "equity-point equity-point-last"
                                : "equity-point"
                        }
                        cx={x(index)}
                        cy={y(point.value)}
                        r={index === series.length - 1 ? 5 : 3}
                    />
                ))}

                {markers.map(({ trade, seriesIndex }) => (
                    <circle
                        key={`marker-${trade.id}`}
                        className="equity-marker"
                        data-decision-id={trade.decision_id}
                        cx={x(seriesIndex)}
                        cy={y(series[seriesIndex].value)}
                        r={7}
                        role="button"
                        tabIndex={0}
                        aria-label={`Operación de la decisión ${trade.decision_id}`}
                        onClick={() => {
                            if (onSelectDecision) {
                                onSelectDecision(trade.decision_id);
                            }
                        }}
                        onKeyDown={(event) => {
                            if (
                                onSelectDecision &&
                                (event.key === "Enter" ||
                                    event.key === " ")
                            ) {
                                event.preventDefault();
                                onSelectDecision(trade.decision_id);
                            }
                        }}
                    />
                ))}

                <text
                    className="equity-axis-label"
                    x={PAD_LEFT}
                    y={HEIGHT - 8}
                    textAnchor="start"
                >
                    {series[0].label}
                </text>

                <text
                    className="equity-axis-label"
                    x={WIDTH - PAD_RIGHT}
                    y={HEIGHT - 8}
                    textAnchor="end"
                >
                    {lastPoint.label}
                </text>
            </svg>

            <p className="equity-note">
                PnL realizado + comisiones por operación sobre el balance
                disponible real; el último punto es el total actual con valor
                de mercado.
            </p>

            <p className="equity-note" data-testid="equity-current">
                Total actual: <strong>${formatMoney(lastPoint.value)}</strong>
            </p>
        </div>
    );
}

export default EquityChart;
