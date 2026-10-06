import KillSwitch from "./KillSwitch";
import ExternalSignalForm from "./ExternalSignalForm";
import TokenField from "./TokenField";
import LivePrices from "./LivePrices";
import { formatMoney } from "../utils/format";

function Sidebar({ balance, marketPrices, onReload, onOperar }) {
    const totalBalance = balance.total_balance_usd || 0;
    const realizedPnl = Number(balance.realized_pnl_usd || 0);
    const realizedClass =
        realizedPnl >= 0 ? "value-positive" : "value-negative";

    return (
        <aside className="sidebar" aria-label="Panel lateral">
            <header className="sidebar-brand">
                <strong>crypto-bot</strong>

                <span>Paper trading · Binance Spot</span>
            </header>

            <article
                className="portfolio-card"
                aria-label="Balance total de la cuenta"
            >
                <span className="eyebrow">Balance total</span>

                <strong className="portfolio-value">
                    ${formatMoney(totalBalance)}
                </strong>

                <span className={`portfolio-change ${realizedClass}`}>
                    PnL realizado: ${formatMoney(realizedPnl)}
                </span>

                <div className="portfolio-actions">
                    <button
                        type="button"
                        className="btn btn-utility"
                        onClick={onReload}
                    >
                        Recargar
                    </button>

                    <button
                        type="button"
                        className="btn btn-utility"
                        onClick={onOperar}
                    >
                        Operar
                    </button>
                </div>
            </article>

            <KillSwitch />

            <ExternalSignalForm />

            <TokenField />

            <LivePrices prices={marketPrices} />
        </aside>
    );
}

export default Sidebar;
