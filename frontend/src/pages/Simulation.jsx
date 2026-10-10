import { useState } from "react";

import TradingPanel from "../components/TradingPanel";
import MetricsPanel from "../components/MetricsPanel";
import HeaderPanel from "../components/HeaderPanel";
import PipelineCanvas from "../components/PipelineCanvas";
import EventStream from "../components/EventStream";
import DecisionInspector from "../components/DecisionInspector";
import EquityChart from "../components/EquityChart";
import AccountSummary from "../components/AccountSummary";
import OpenPositions from "../components/OpenPositions";
import TradeHistory from "../components/TradeHistory";
import LearningTab from "../components/LearningTab";
import NavRail from "../components/NavRail";
import SectionTabs from "../components/SectionTabs";
import Sidebar from "../components/Sidebar";

import useSimulationData from "./useSimulationData";

function Simulation() {
    const {
        account,
        summary,
        balance,
        positions,
        trades,
        marketPrices,
        loading,
        error,
        reload,
    } = useSimulationData();

    const [tab, setTab] = useState("operar");
    const [selectedDecisionId, setSelectedDecisionId] =
        useState(null);

    if (loading) {
        return (
            <main className="simulation-page">
                <div className="loading-state">
                    Cargando simulación...
                </div>
            </main>
        );
    }

    if (error) {
        return (
            <main className="simulation-page">
                <div className="form-message error">
                    {error}
                </div>
            </main>
        );
    }

    if (!account || !summary) {
        return (
            <main className="simulation-page">
                <div className="empty-state">
                    No hay una cuenta de simulación disponible.
                </div>
            </main>
        );
    }

    const accountBalance = balance || summary.balance || {};
    const availableBalance = accountBalance.available_usd || 0;

    return (
        <div className="app-shell">
            <NavRail active={tab} onSelect={setTab} />

            <main className="workspace" id="workspace">
                <header className="workspace-header">
                    <div className="page-heading">
                        <span className="eyebrow">
                            PAPER TRADING
                        </span>

                        <h1>Simulación</h1>

                        <p>
                            Opera con dinero ficticio sin afectar
                            fondos reales.
                        </p>
                    </div>

                    <div className="simulation-badge">
                        <span className="status-dot" />
                        SIMULACIÓN ACTIVA
                    </div>
                </header>

                <AccountSummary
                    account={account}
                    balance={accountBalance}
                />

                <HeaderPanel />

                <SectionTabs value={tab} onChange={setTab} />

                <div
                    className="tab-panel"
                    role="tabpanel"
                    id="panel-operar"
                    aria-labelledby="tab-operar"
                    hidden={tab !== "operar"}
                    tabIndex={0}
                >
                    <div className="operar-grid">
                        <section className="data-section equity-section">
                            <div className="section-header">
                                <div>
                                    <span className="eyebrow">
                                        EQUITY
                                    </span>

                                    <h2>Curva de equity</h2>
                                </div>
                            </div>

                            <EquityChart
                                trades={trades}
                                availableBalance={
                                    accountBalance.available_usd
                                }
                                currentTotal={
                                    accountBalance.total_balance_usd
                                }
                                onSelectDecision={(decisionId) => {
                                    setSelectedDecisionId(decisionId);
                                    setTab("consola");
                                }}
                            />
                        </section>

                        <TradingPanel
                            accountId={account.id}
                            marketPrices={marketPrices}
                            positions={positions}
                            availableBalance={availableBalance}
                            onOrderExecuted={reload}
                        />
                    </div>
                </div>

                <div
                    className="tab-panel"
                    role="tabpanel"
                    id="panel-estado"
                    aria-labelledby="tab-estado"
                    hidden={tab !== "estado"}
                    tabIndex={0}
                >
                    <MetricsPanel />
                </div>

                <div
                    className="tab-panel"
                    role="tabpanel"
                    id="panel-consola"
                    aria-labelledby="tab-consola"
                    hidden={tab !== "consola"}
                    tabIndex={0}
                >
                    <div className="history-stack">
                        <PipelineCanvas />
                        <EventStream />
                        <DecisionInspector
                            selectedDecisionId={selectedDecisionId}
                            onSelect={setSelectedDecisionId}
                        />
                    </div>
                </div>

                <div
                    className="tab-panel"
                    role="tabpanel"
                    id="panel-learning"
                    aria-labelledby="tab-learning"
                    hidden={tab !== "learning"}
                    tabIndex={0}
                >
                    <LearningTab />
                </div>

                <div
                    className="tab-panel"
                    role="tabpanel"
                    id="panel-historial"
                    aria-labelledby="tab-historial"
                    hidden={tab !== "historial"}
                    tabIndex={0}
                >
                    <div className="history-stack">
                        <OpenPositions positions={positions} />

                        <TradeHistory trades={trades} />
                    </div>
                </div>
            </main>

            <Sidebar
                balance={accountBalance}
                marketPrices={marketPrices}
                onReload={reload}
                onOperar={() => setTab("operar")}
            />
        </div>
    );
}

export default Simulation;
