# Crypto trading bots and AI/LLM trading systems: credibility, real results, lessons for a solo Python bot (as of Oct 2026)

Labels used: **[VERIFIED]** = primary source or multiple independent reputable reports; **[REPORTED]** = single secondary/media source, not independently checked; **[UNVERIFIED]** = vendor/author claim or my background knowledge not confirmed in this session.

## 1. Open-source frameworks: Freqtrade (incl. FreqAI), Hummingbot, Jesse, OctoBot, NautilusTrader, vectorbt

### Takeaway
Freqtrade is the most mature and widely used open-source crypto bot (around 49k GitHub stars as of April 2026). Its documentation openly warns that backtests can "cheat" through look-ahead bias, and it ships tools to detect this. Jesse is stronger for research-style backtesting (walk-forward), and Hummingbot targets market making and arbitrage. None of the frameworks publishes verified aggregate live profitability. Community strategy results are backtests, not audited track records.

### Cited Findings
- **GitHub stars, April 2026** [REPORTED]: Freqtrade 49,426 (GPLv3), Hummingbot 18,363 (Apache 2.0), Jesse 7,795 (LGPL-3.0). All three were updated in April 2026. — [Pi Stack comparison, 2026-04-27](https://www.pistack.xyz/posts/2026-04-27-freqtrade-vs-jesse-vs-hummingbot-self-hosted-algorithmic-trading-guide-2026/)
- **Freqtrade features** [REPORTED]:
  - Built-in backtesting and hyperopt (scikit-optimize)
  - Dry-run mode
  - 20+ exchanges via CCXT
  - FreqUI dashboard and Telegram integration
  - Official Docker image and compose file
  - Stop-loss, ROI, trailing stop and custom risk tools
  - Source: [Pi Stack](https://www.pistack.xyz/posts/2026-04-27-freqtrade-vs-jesse-vs-hummingbot-self-hosted-algorithmic-trading-guide-2026/)
- **Jesse** [REPORTED]: The article calls its backtesting "exceptionally thorough," with candle-by-candle simulation, walk-forward and portfolio-level testing. Its community is smaller, and the full UI is commercial. — [Pi Stack](https://www.pistack.xyz/posts/2026-04-27-freqtrade-vs-jesse-vs-hummingbot-self-hosted-algorithmic-trading-guide-2026/)
- **Hummingbot** [REPORTED]: It has 30+ CEX, DEX and derivatives connectors and is purpose-built for market making and arbitrage. Its backtesting is limited. — [Pi Stack](https://www.pistack.xyz/posts/2026-04-27-freqtrade-vs-jesse-vs-hummingbot-self-hosted-algorithmic-trading-guide-2026/)
- **Freqtrade lookahead-analysis** [VERIFIED, official docs]:
  - Backtesting computes indicators on the full dataframe, so signals that peek at future candles inflate results. The `lookahead-analysis` command re-runs backtests per signal and compares them against a baseline to flag biased entries, exits and indicators.
  - The docs warn that removing the bias "usually makes [a strategy] significantly worse." Biased strategies found online are often not worth salvaging.
  - Caveat: the tool checks only signals that actually trigger, so false negatives are possible.
  - Source: [Freqtrade docs: Lookahead analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- **FreqAI** [VERIFIED, official docs]:
  - Models retrain periodically during live deployment.
  - The backtesting module emulates periodic retraining on historic data.
  - Outliers are removed from training and prediction data.
  - There are eight example models, including LightGBMRegressor, classifiers and a CNN, plus a separate reinforcement-learning module.
  - Caveats: the example strategy is labelled "Not for production." FreqAI is incompatible with dynamic pairlists that add or remove pairs. The project has no token and sells no signals.
  - Source: [Freqtrade docs: FreqAI](https://www.freqtrade.io/en/stable/freqai/)

### Inferences
- For a solo developer writing a custom FastAPI + Binance Spot bot, Freqtrade is the reference implementation to copy ideas from: the dry-run vs live separation, lookahead and recursive analysis, protections, Telegram control, and the per-trade database. Running the strategy inside Freqtrade instead of writing an execution engine from scratch would remove a large class of bugs.
- The Pi Stack table describes Freqtrade as spot-focused. From background knowledge, Freqtrade has supported futures (Binance, Bybit, OKX and others) since about 2022 [UNVERIFIED in this session]. For a Spot-only bot the distinction does not matter.
- Background knowledge on the remaining frameworks [UNVERIFIED in this session]:
  - NautilusTrader: Rust core with Python API, event-driven, the same code for backtest and live; institutional-grade but with a steeper learning curve.
  - vectorbt: vectorized research and backtesting library with no live trading in the open-source version; vectorbt PRO is paid.
  - OctoBot: GUI-oriented bot with grid, DCA and AI/ChatGPT evaluators and a cloud offering.

### Gaps
- I found no audited or aggregated statistics on live profitability for Freqtrade, Hummingbot, Jesse or OctoBot users. Such statistics do not appear to exist.
- I did not verify current (Oct 2026) star counts or release versions for NautilusTrader, vectorbt or OctoBot.
- I found no quality Reddit or forum post-mortems; the search returned low-quality pages. Practitioner reality checks rest mainly on the official Freqtrade warnings.

## 2. Commercial bots: Pionex, 3Commas, Cryptohopper, Bitsgap, Binance native bots

### Takeaway
I found **no audited or independently verified statistics on user profitability** for any commercial bot platform. Marketing figures (e.g., "X% of grid bots profitable") are vendor claims selected over chosen windows. The best-documented risk fact is security: in December 2022, 3Commas API keys leaked and were used against users.

### Cited Findings
- **3Commas API-key leak** [VERIFIED]:
  - 3Commas CEO Yuriy Sorokin confirmed in December 2022 that files published by a hacker were genuine ("the data in the files is true").
  - 3Commas asked Binance, KuCoin and other exchanges to revoke all keys linked to 3Commas.
  - Binance declined to reimburse an affected user and urged users to disable their 3Commas keys. Users reported the leaked keys being used to pump low-cap coins.
  - Sources: [Cointelegraph, 2022-12-28](https://cointelegraph.com/news/3commas-ceo-confirms-api-key-leak-following-warning-from-cz); [Bitdefender on FBI probe reports](https://bitdefender.com/blog/hotforsecurity/the-fbi-is-reportedly-probing-3commas-after-api-keys-leaked-on-twitter)
- Pionex publishes grid-bot FAQs, but I found no profitability statistics there. — [Pionex grid bot FAQ](https://intercom.help/pionex/en/articles/15500905-grid-trading-bot-faq)
- Binance Square pages for grid bots are user posts and screenshots of selected wins, not platform statistics. — [Binance Square #gridbot](https://www.binance.com/square/hashtag/gridbot)

### Inferences
- Grid and DCA bots are profitable mainly in range-bound markets. In strong downtrends they accumulate losing inventory, and in strong uptrends they sell too early. This is structural, but I found no 2026 data source quantifying it [background knowledge].
- Lesson for the solo bot:
  - Use Binance API keys with trading enabled, withdrawals disabled and an IP whitelist.
  - Never give keys to third-party platforms.
  - This is the main lesson from the 3Commas incident.

### Gaps
- No verified per-user profitability statistics were found for Pionex, 3Commas, Cryptohopper, Bitsgap or Binance native bots (grid, DCA, rebalancing). If they exist, they are vendor marketing and should be treated as unverified.

## 3. LLM trading experiments with real money: Alpha Arena, academic papers, live fleets

### Takeaway
When LLMs were given real money to trade directly, results were mostly negative and highly variable:
- **Alpha Arena Season 1** (crypto perps, Oct–Nov 2025): 4 of 6 models lost roughly 42–59%. GPT-5 and Gemini 2.5 Pro were among the worst.
- **Season 1.5** (US stocks): most models were at a loss.
- **A September 2026 production study of 500+ agents** found no directional edge, volatility-blind sizing and large liquidation losses.

Academic benchmarks agree: most LLM agents fail to beat buy-and-hold, and the agent framework matters more than the model. The evidence favours LLMs as analysts and summarizers inside a rule-based risk shell, not as autonomous decision-makers.

### Cited Findings
- **Alpha Arena Season 1** (Nof1) [VERIFIED by multiple reports; on-chain wallets were public]:
  - Dates: about Oct 17/18 to Nov 3, 2025.
  - Setup: $10,000 per model, crypto perpetuals on Hyperliquid (e.g., BTC, SOL, DOGE). Models had to generate ideas, size trades and manage risk on their own, with all outputs public.
  - Final balances:

    | Rank | Model | Final balance | Return |
    |---|---|---|---|
    | 1 | Qwen3 Max | $12,231 | +22.3% |
    | 2 | DeepSeek | $10,489 | +4.9% |
    | 3 | Claude Sonnet 4.5 | $5,799 | −42.0% |
    | 4 | Gemini 2.5 Pro | $5,445 | −45.5% |
    | 5 | Grok | $4,208 | −57.9% |
    | 6 | GPT-5 | $4,126 | −58.7% |

  - Sources: [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/); [Decrypt](https://decrypt.co/345006/ai-crypto-trading-showdown-deepseek-grok-winning-gemini-implodes); [SCMP](https://www.scmp.com/tech/tech-trends/article/3329784/deepseek-outperforms-ai-rivals-real-money-real-market-crypto-showdown)
- **Nof1 founder Jay Azhang on the design** [REPORTED]: he said "LLMs do not handle numerical time series data well, but that was the entire context we provided them," and that models had "a limited set of assets and a rather narrow action space." — [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/)
- **Rankings were unstable** [REPORTED]: early on (Oct 20, 2025), Grok, DeepSeek and Claude were each up more than 25%. Grok and Claude later finished down 42–58%. DeepSeek had peaked above $13k before falling back. — [Decrypt](https://decrypt.co/345006/ai-crypto-trading-showdown-deepseek-grok-winning-gemini-implodes); [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/)
- **Gemini 2.5 Pro behaviour** [REPORTED]: it was described as making "frequent, erratic trading" decisions and flipping between bearish and bullish at great loss. GPT-5 was largely inactive early on. — [Decrypt](https://decrypt.co/345006/ai-crypto-trading-showdown-deepseek-grok-winning-gemini-implodes)
- **Alpha Arena Season 1.5** (Nov–early Dec 2025) [REPORTED]:
  - Format: US stocks instead of crypto, with modes New Baseline, Monk Mode, Situational Awareness and Max Leverage.
  - Results: a "Mystery Model," identified as Grok 4.20, won with about +12% in two weeks. GPT-5.1 was 2nd and Gemini 3 was 3rd. As of Dec 8, 2025, only Grok 4.20 was still profitable overall.
  - Source: [ForkLog, 2025-12-08](https://forklog.com/en/ai-model-grok-4-2-triumphs-in-trading-tournament/)
- **"What LLM Trading Agents Actually Do in Production"** (arXiv 2609.05663, Sept 2026, DX Research Group) [VERIFIED as a preprint; not peer reviewed; several results self-labelled provisional]:
  - Two fleets:
    - DX Terminal Pro: 3,505 user-funded vaults running Qwen3-235B on real ETH memecoins on Base, Feb–Mar 2026.
    - DXAP: about 500–600 agents on Hyperliquid perps, Jun–Aug 2026, mostly paper trading with a small real-money book.
  - Findings:
    - The operating layer drives behaviour more than strategy text. A risk slider drives leverage, and agent identity explains 60% of variance.
    - Median leverage was 5.0x in every volatility bucket (volatility-blind sizing).
    - 43.2% of positions reached +300 bps of favourable excursion, but 49.3% of those still closed at a loss. A fixed 2%/4% stop/target bracket would have added about +39 bps per position.
    - DXAP lost about −$217K realized P&L, with a 41% win rate vs 50% for matched retail.
    - In a replay league, frontier models' decision quality was statistically indistinguishable.
    - Prompt fixes failed: agents asked to state their liquidation distance did not size down and were liquidated more often.
  - Recommendations: put protections in the order path (atomic brackets, volatility-scaled leverage in the tool, not the prompt), add post-order risk checks, and keep a decision-provenance ledger.
  - Source: [arXiv 2609.05663](https://arxiv.org/abs/2609.05663)
- **StockBench** (arXiv 2510.02209) [VERIFIED as a preprint]: a contamination-free, multi-month stock-trading simulation with prices, fundamentals and news. Most LLM agents failed to beat buy-and-hold, and strong financial-QA scores did not predict good trading. — [arXiv 2510.02209](https://arxiv.org/abs/2510.02209v1)
- **Agent Market Arena** (arXiv 2510.11695) [VERIFIED as a preprint]:
  - Setup: live evaluation Aug 1–Sep 30, 2025 on TSLA, BMRN, BTC and ETH. Models included GPT-4o, GPT-4.1, Gemini-2.0-flash, Claude-3.5-haiku and Claude-sonnet-4.
  - Changing the agent framework produced far more variation than changing the LLM backbone.
  - Buy & Hold (+46.88%) beat most agents on TSLA.
  - Only two months of data, with no significance testing.
  - Source: [arXiv 2510.11695](https://arxiv.org/abs/2510.11695)
- **"The Alpha Illusion"** (Ye et al., 2026), as summarized by a Substack review [REPORTED]:
  - Headline LLM-trading alpha often comes from short windows inside the model's training data (temporal contamination). Performance can collapse past the knowledge cutoff.
  - Other problems: short samples, multiple testing, and unmodelled costs and liquidity. A model's stated confidence is not a tradable probability.
  - The paper proposes a modular design that separates extraction, forecasting, calibration, risk, sizing and execution.
  - Source: [Harbourfront Quant](https://harbourfrontquant.substack.com/p/how-effective-are-llm-trading-agents)
- **TradingAgents** (multi-agent LLM framework, arXiv 2412.20138) exists as a popular open-source framework. I did not verify its reported results in this session. — [arXiv 2412.20138](https://arxiv.org/pdf/2412.20138)
- **Look-ahead bias** in LLM forecasts is an active research area in 2025–26, including the Look-Ahead-Bench benchmark. — [arXiv 2601.13770](https://arxiv.org/pdf/2601.13770); [arXiv 2512.23847](https://arxiv.org/pdf/2512.23847)

### Inferences
- **Do not let Gemini decide or size trades.** Every real-money data point (Alpha Arena S1, DXAP) shows LLMs trading directly have no reliable edge and poor risk control. Gemini 2.5 Pro specifically lost about 45% in S1. A Gemini 3-class model placed 3rd in S1.5, but over only about two weeks, which is statistically meaningless.
- **Any backtest that uses an LLM on past dates is suspect**, because the model may "know" what happened. Evaluate the LLM component only forward (paper trading) after its knowledge cutoff.
- **What to copy from the DXRG study:**
  - Hard-coded stop and take-profit brackets placed atomically with each entry (on Binance Spot, OCO orders).
  - Position size computed from realized volatility in code.
  - A ledger that records exactly what the model saw and said for every decision.
  - Treat Gemini output as one feature or veto, never the final word.
- **Alpha Arena's sample size is tiny**: six models, about two weeks, one market regime. Rank order flipped repeatedly, so do not pick a model based on Arena rankings.

### Gaps
- I could not confirm a full Alpha Arena Season 2 (2026) with published results; searches returned nothing relevant. Nof1's own site was not fetched.
- FinMem and other per-paper numbers were not verified in this session.
- I found no rigorous study of an LLM used only as a news or sentiment feature in a live crypto system with out-of-sample P&L.

## 4. Best practices for an "AI that learns": ML retraining, regime detection, meta-labeling, overfitting, safe LLM use

### Takeaway
The credible pattern is a rule-based or classical-ML core with:
- strict anti-overfitting validation (lookahead and recursive checks, walk-forward, out-of-sample);
- periodic retraining that is itself backtested (FreqAI-style);
- deterministic risk controls;
- the LLM limited to summarizing news and sentiment, sanity-checking proposed trades, and journaling.

The "AI that learns" should learn slowly and be validated forward. It should not self-modify live strategy logic.

### Cited Findings
- **FreqAI** emulates periodic retraining in backtests and retrains during live deployment. — [Freqtrade FreqAI docs](https://www.freqtrade.io/en/stable/freqai/)
- **Look-ahead bias** inflates backtests, and removing it usually makes strategies significantly worse. — [Freqtrade lookahead docs](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- **Jesse's walk-forward optimization** is positioned as a way to reduce overfitting. — [Pi Stack](https://www.pistack.xyz/posts/2026-04-27-freqtrade-vs-jesse-vs-hummingbot-self-hosted-algorithmic-trading-guide-2026/)
- **Production LLM agents**: prompt-level risk instructions did not change behaviour, while risk logic in the tool or order path did. — [arXiv 2609.05663](https://arxiv.org/abs/2609.05663)
- **Recommended LLM-system design**: separate information extraction, forecasting, calibration, risk, sizing and execution, log what the agent saw at each decision, and publish losing trades. — [Harbourfront Quant review of "The Alpha Illusion"](https://harbourfrontquant.substack.com/p/how-effective-are-llm-trading-agents)
- **Agent Market Arena** found that architecture matters more than model choice. — [arXiv 2510.11695](https://arxiv.org/abs/2510.11695)

### Inferences
- **Practical architecture for a FastAPI + Binance Spot + Gemini bot:**
  1. Deterministic signal engine, with optional LightGBM trained on features using walk-forward retraining (e.g., weekly), validated with purged or embargoed splits.
  2. A regime filter (trend vs range via ADX or volatility percentile) that switches between strategy families.
  3. Gemini, called a few times per day, returns structured JSON: news and sentiment score, event-risk flag, and a "does this trade make sense" veto with its reasons. Its output is logged and can only reduce or block exposure, never increase it.
  4. A hard risk layer: maximum position as a percentage of equity, a daily loss limit/kill switch, OCO brackets, and a minimum notional for Binance filters.
  5. A journal: Gemini writes a daily post-trade summary into the DB for human review.
- **Meta-labeling** (López de Prado): a secondary model predicts whether the primary signal will be right and sizes accordingly. It fits naturally with "Gemini as veto." I found no 2026 crypto-specific evidence in this session [background knowledge].
- **Measure the LLM's value directly**: track the strategy with and without the Gemini veto in parallel (paper), and keep the veto only if it measurably improves out-of-sample results after costs.

### Gaps
- No independently verified live track records were found for FreqAI or regime-detection systems.
- No quantitative studies were found on how often retrained crypto ML models degrade (e.g., decay half-life).

## 5. Running the bot locally on Windows: Task Scheduler vs service (NSSM), reliability, when to move to a VPS

### Takeaway
For a bot that must start on login and run several times per day, two setups work:
- **Task Scheduler**: fine for short, discrete runs, e.g. a Python script triggered at fixed times with "run whether user is logged on or not."
- **A Windows service via NSSM**: better for a long-running FastAPI process, because NSSM restarts the process if it crashes.

A home PC adds risks from sleep and hibernation, Windows Update reboots, network loss and clock drift. Move to a cheap VPS once real money is live or the bot holds open positions that need monitoring 24/7.

### Cited Findings
- **NSSM**:
  - Keeps a constantly running application alive and "will attempt to start it up again" if it fails or crashes.
  - Can run a tool once at startup or retry a script until it succeeds.
  - Integrates with the Windows service Recovery actions and logs to the Windows Event Log.
  - Source: [NSSM scenarios](https://nssm.cc/scenarios)
- **Tutorial**: running a Python script as a Windows service with NSSM. — [MSSQLTips](https://www.mssqltips.com/sqlservertip/7325/how-to-run-a-python-script-windows-service-nssm/)

### Inferences
- **Background knowledge** [UNVERIFIED in this session]:
  - NSSM's last stable release is 2.24 (2014), with only pre-release builds since. It still works widely, but it is effectively unmaintained. Alternatives: WinSW, or Servy.
  - Task Scheduler can trigger "At log on" or "At startup," repeat every N hours, and restart on failure. It does not supervise long-running processes as robustly.
  - "Start on login" means the bot will not run after a reboot until the user logs in. "At startup" with "run whether user is logged on or not" avoids this.
- **Recommended setup:**
  - Run the FastAPI app as an NSSM/WinSW service, with scheduling inside the app (APScheduler), or use Task Scheduler jobs that call the API.
  - Disable sleep, set Windows Update active hours, keep time in sync (Binance rejects requests whose timestamps are outside `recvWindow`), and log to files with rotation.
  - Have the bot send heartbeat alerts (e.g., Telegram) so silent failures are noticed.
- **Move to a VPS** (Linux plus Docker, as Freqtrade officially supports) when:
  - real funds are deployed;
  - positions depend on the bot being online, and exchange-side OCO or stop orders are not enough;
  - uptime and IP-whitelist stability matter.
- **Note on location**: Binance blocks some jurisdictions. VPS location must comply with Binance's terms; do not use a VPS to bypass geo-restrictions.

### Gaps
- I did not fetch Microsoft's Task Scheduler documentation or verify NSSM's maintenance status in this session.
- I found no empirical uptime comparisons between home PCs and VPSs for trading bots.
