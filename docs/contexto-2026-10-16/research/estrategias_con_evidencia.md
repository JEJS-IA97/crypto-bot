# Systematic crypto strategies with credible evidence of positive net returns (small retail account, Binance Spot) — research notes, as of Oct 2026

Context: user's ORB bot (NY 9:00-10:00, 5m candles, BTC/ETH/BNB/SOL/ADA, long-only spot), 12-month walk-forward: -14% net, 354 trades, 15% win rate, PF 0.24, costs (0.1%/side + 0.05% slippage = ~0.30% round trip) = 14 USD on 20 USD capital. Buy & hold positive on BTC/ETH/BNB/SOL over the same period.

Evidence-quality legend used below: [PEER] = peer-reviewed journal; [WP] = working paper / preprint (SSRN, arXiv, NBER) not yet peer-reviewed; [PRAC] = practitioner/vendor research; [MKT] = marketing/commercial interest.

## 1. Time-series momentum / trend following (daily/4h MA, Donchian, volatility targeting)

### Takeaway
This is the best-documented positive-net-of-cost strategy family in crypto: long-only trend filters on daily (or multi-hour) bars, held days-to-weeks, show net Sharpe ~1-1.5 vs ~0.8 for buy & hold, with the gain coming mostly from cutting drawdowns (exiting bear markets), not from higher bull-market returns. Profits are concentrated in bull regimes; the short side generally loses. Intraday versions are much weaker.

### Cited Findings
- [PEER] Liu & Tsyvinski, "Risks and Returns of Cryptocurrency", Review of Financial Studies 34(6):2689-2727 (2021; NBER WP w24877, 2018). Sample BTC 2011–May 2018. Strong time-series momentum: a 1-SD weekly BTC return (16.64%) predicts +3.16%, +3.66%, +3.49%, +1.50% over the next 1–4 weeks; daily returns predict returns 1–6 days ahead. Effect smaller but still significant from 2013 onward and out of sample. Returns reported gross (no transaction-cost analysis). Exposure to stock factors (SMB, MOM) not stable — [NBER PDF](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf); [RePEc record](https://ideas.repec.org/a/oup/rfinst/v34y2021i6p2689-2727..html)
- [WP, data to Aug 2023] Han, Kang & Ryu, "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions". Best long-only TSMOM (28-day lookback, 5-day hold), 15 bps per trade costs: Sharpe 1.51 after costs vs 0.85 market; max drawdown ~62% vs ~89% for market; invested only ~48% of the time. Advantage comes mainly from lower downside risk. Short-only and long-short versions worse than long-only. TSMOM concentrated in bull markets — [AUT/ACFR PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)
- [WP, Apr 2025] Zarattini, Pagani & Barbon, "Catching Crypto Trends: A Tactical Approach for Bitcoin and Altcoins" (SSRN 5209907). Survivorship-bias-free data on 21,616 coins, Jan 2010–Mar 2025. Rules: long-only; enter when daily close > max close of lookback N, N ∈ {5,10,20,30,60,90,150,250,360} days; exit on trailing stop = max(previous stop, midpoint of N-day max/min closes); size each to 25% annualized target vol (90-day stdev), leverage cap 200%; equal-weight ensemble across lookbacks, daily rebalance; costs tested at 0.10/0.25/0.50% per trade. Rotational portfolio of top-20 liquid coins: net Sharpe "above 1.5", 10.8% annualized alpha vs BTC. CAGR/MDD not in abstract — [Concretum summary](https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/); [CXO rules summary](https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/); [Barbon page](https://abarbon.com/papers/catching-crypto-trends)
- [WP, ~2020] Rozario, Holt, West, Ng, "A Decade of Evidence of Trend Following Investing in Cryptocurrencies" (arXiv 2009.12155). BTCUSD Bitstamp hourly Sep 2011–Dec 2019; SMA/EMA/DEMA crossovers with yearly walk-forward. Best Sharpe 1.09–1.35 (in-sample optimum); simple ~10/40-day SMAs had Sharpe mostly 0.5–1.5 with "slight drop-off in recent years"; recent walk-forward slices Sharpe < 1. Costs assumed negligible (a weakness). Explicitly: "No profitable intraday strategies were found for BTCUSD spot." — [arXiv/ar5iv](https://ar5iv.labs.arxiv.org/html/2009.12155)
- [PEER] Hudson & Urquhart, "Technical trading and cryptocurrencies", Annals of Operations Research 297(1):191-220 (online 2019, print 2021). 14,919 rules (MA, filter, support-resistance, oscillator, channel breakout) on BTC/LTC/XRP/ETH to end-2017. After data-snooping corrections (bootstrap + Bonferroni/Holm/BH/BY), ~20–50% of rules remain significant. Breakeven costs 7.9 bps (S/R on LTC) to 147.6 bps (filter rule on ETH); most rule classes have many rules with breakeven > 50 bps. Out of sample (H1 2018) rules did NOT produce positive returns for Bitcoin — [Springer](https://link.springer.com/article/10.1007/s10479-019-03357-1)
- [WP, Feb 2026; vendor-authored] Bui & Nguyen (Talyxion Research), "Systematic Trend-Following with Adaptive Portfolio Construction" (arXiv 2602.11708). 6h bars, Binance perps, 150+ pairs, OOS Jan 2022–Dec 2024, 4 bps taker + slippage + funding. Benchmarks in their Table 1: Vol-scaled TSMOM Sharpe 1.83, MDD -16.1%; plain TSMOM-1M Sharpe 0.65, MDD -34.8%; BTC buy & hold Sharpe 0.17, MDD -64.1%. Their own system Sharpe 2.41 (but computed with 0% risk-free vs 4.5% for benchmarks; date inconsistencies; capacity-limited; needs shorting via futures). Timeframe comparison net of 4 bps: H1 Sharpe 1.54, H4 2.08, H6 2.41, D1 1.63; Sharpe falls from 2.87 (0 bps) to 1.62 (12 bps). Bear-regime return -4.2%/yr. Treat as low-credibility — [arXiv](https://arxiv.org/html/2602.11708v1)
- [PRAC, Jan 2026] Concretum (Pagani) "Seasonality in Bitcoin Intraday Trend Trading": high-frequency trend ensemble, 20% vol target, 2018–2025, gross Sharpe ~1.6 vs ~0.8 for vol-targeted long BTC; returns concentrated from Sunday ~19:00 NY (Tokyo open) for ~24h; US Sunday morning negative. No net-of-cost figures — [Concretum](https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/)

### Inferences
- The consistent pattern across sources: trend following works in crypto as a drawdown-reduction overlay on a long position (sit in stablecoin during downtrends), with holding periods of days to weeks and low trade counts (tens per year per asset, not hundreds).
- For a long-only spot bot, the realistic expectation is similar-to-somewhat-lower returns than buy & hold in strong bull years, much smaller drawdowns in bear years, and Sharpe ~1–1.5 over full cycles; whipsaw losses in sideways markets are the main cost.
- In-sample optimized parameters (e.g., Rozario's best pairs) overstate; ensembles across many lookbacks (Zarattini) are a robustness device that reduces parameter-selection risk.

### Gaps
- Full-text CAGR/MDD for Zarattini et al. not retrievable (SSRN abstract only).
- No peer-reviewed study found covering 2024–2026 out-of-sample for simple daily MA/Donchian rules on Binance spot specifically.

## 2. Cross-sectional momentum / relative-strength rotation among top coins

### Takeaway
Evidence is mixed and weaker than time-series momentum. It appears mainly in liquid coins and in the long leg; the short leg is destroyed by jumps. A long-only "hold the strongest few large caps, go to stablecoin when all are weak" hybrid is better supported than pure cross-sectional long-short.

### Cited Findings
- [WP, 2019] Begušić & Kostanjčar, "Momentum and liquidity in cryptocurrencies" (arXiv 1904.00890), Jan 2015–Jan 2019, 711 coins: strong momentum only in the most liquid coins (winners-minus-losers +0.26%/day); negative in neutral/illiquid brackets; illiquid losers show reversal. Liquid-winners long-only information ratio 1.59 at 0 bps → 1.27 at 100 bps — [arXiv](https://ar5iv.arxiv.org/html/1904.00890)
- [WP, data to 2023] Han, Kang & Ryu: best CSMOM (14-day lookback, 7-day hold) Sharpe 1.28 vs 1.01 market, but only 6 of 21 portfolios beat market and 5 were liquidated; only 3 remain t>2 using log returns; profit mostly from long leg; "cross-sectional evidence weak", TSMOM "clearly stronger" — [AUT PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)
- Liu & Tsyvinski (RFS 2021) cite Stoffels (2017) for cross-sectional momentum across 15 coins but do not test it themselves — [NBER PDF](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf)
- Zarattini et al.'s best result is itself a rotation among top-20 liquid coins driven by trend signals (Sharpe >1.5 net) — [Concretum](https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/)

### Inferences
- For a spot-only bot with few hundred USD: rank a small liquid universe (e.g., BTC, ETH, BNB, SOL) weekly by 2–4 week return, hold top 1–2 only if their own trend filter is positive, else USDT. Weekly rebalancing keeps trades low.
- Small coins (ADA-like mid-caps and below) are more likely to show reversal than momentum and have wider spreads.

### Gaps
- No rigorous OOS study found on a 4–5 coin top-cap-only rotation on Binance spot post-2023.

## 3. Mean reversion / grid bots

### Takeaway
Short-horizon mean reversion is statistically real in crypto but too small to beat retail taker costs; grid bots are essentially short-volatility/range bets that earn in sideways markets and lose heavily (holding a falling bag or missing the rally) on trending breaks. No peer-reviewed evidence of net-profitable retail grid bots was found.

### Cited Findings
- [WP, Aug 2026] Kitron & Wengrowicz, "Short-horizon mean reversion in cryptocurrency markets" (arXiv 2608.21888). 15-min candles, 183 Binance USDT spot pairs, 2025-01-01 to 2026-02-11 + holdout to 2026-08-08. 90% of crypto pairs show significant directional reversal (vs 2.7% of US stocks); effect decays within ~4h. Gross edge peaks ~1.3 bps per trade — below a 5 bp maker round trip and far below 10–20 bp taker costs; "none of the 183 pairs clears the 5 bp maker band" — [arXiv PDF](https://arxiv.org/pdf/2608.21888); [RePEc](https://ideas.repec.org/p/arx/papers/2608.21888.html)
- [WP, 2019] Illiquid losers show reversal (1.07%/day vs 0.53% for illiquid winners), but authors warn spreads in illiquid coins likely erase it — [arXiv](https://ar5iv.arxiv.org/html/1904.00890)
- Search for academic grid-bot evidence returned only GitHub code, Binance Square posts and forum material (marketing/anecdote, not evidence) — e.g. [Binance Square #GridBot](https://www.binance.com/square/hashtag/GridBot)

### Inferences
- Grid on spot = repeatedly buying dips/selling rips inside a band: profit per grid step must exceed ~0.15–0.30% round trip; in a downtrend below the band you end fully in the coin with unrealized loss; above the band you end fully in USDT and miss the move. Expected outcome over long horizons ≈ worse than buy & hold in trending markets.
- Intraday mean reversion is a market-maker game (rebates, latency); not viable at retail fee tiers.

### Gaps
- No credible, peer-reviewed or audited OOS study of Binance grid bot net returns found.

## 4. DCA, DCA + trend filter, value averaging, rebalancing premium

### Takeaway
DCA does not raise expected return (lump sum wins most of the time in a rising asset) but materially reduces drawdowns at similar risk-adjusted return; for a 40-to-few-hundred USD account with ongoing contributions, DCA is the natural baseline. Rebalancing-premium claims for crypto are mostly theoretical/marketing.

### Cited Findings
- [PRAC/MKT, Apr 2023] Amdax (Stolte), BTC ~2012–2022, 0.7% fee/transaction: lump sum average annual return >3x DCA; lump sum max drawdown on average ~20 pp deeper; Calmar ratios "practically identical" on average; weekly DCA least risky. Author's firm sells a DCA plan — [Medium/Amdax](https://medium.com/amdax-asset-management/lump-sum-or-dollar-cost-averaging-42c8f5bb9938)
- [MKT, Apr 2026] Hashdex CIO note on rebalancing/Shannon's demon: only a hypothetical coin-flip example, no measured crypto rebalancing premium; BTC 30-day vol "often below 50%" by 2026 (vs >150% early years) — [Hashdex](https://hashdex.com/en-CH/insights/a-hidden-return-engine-harnessing-crypto-s-volatility-through-rebalancing)

### Inferences
- Lower crypto vol (≤50%) shrinks the theoretical rebalancing (volatility-harvesting) bonus, which scales with variance; BTC/ETH high correlation further shrinks it. Expect small effect; rebalance infrequently (monthly/threshold bands) to keep fees negligible.
- "DCA + trend filter" (buy weekly only when price > 200d MA, else accumulate USDT and deploy on regain) combines sections 1 and 4; no rigorous published OOS study found — treat as a reasonable but unproven heuristic.

### Gaps
- No peer-reviewed study found on value averaging or DCA-with-trend-filter in crypto.

## 5. Funding-rate / basis carry (cash-and-carry)

### Takeaway
Real, low-directional-risk yield but it requires a short perpetual/futures leg (Binance Futures or similar) — not achievable spot-only. Yields compressed in 2024–2025 toward the ~11%/yr baseline or below on Binance (~6%/yr Q3 2025), roughly comparable to T-bills; with a 40–300 USD account, fees and minimum sizes make it marginal.

### Cited Findings
- [PRAC, BitMEX Q3 2025 derivatives report] Baseline interest component 0.01%/8h ≈ 10.95% annualized; funding positive >92% of Q3 2025. Mean 8h funding Q3 2025: BTC Binance 0.0057%, ETH Binance 0.0060% (≈6.2% and ≈6.6% annualized by 1,095 periods/yr — my calculation); BitMEX BTC 0.0081% (~8.9%); Hyperliquid higher/more volatile. 2024–2025 cycle "hovering near baseline"; early bull markets sometimes >0.2%/8h — [BitMEX blog](https://blog.bitmex.com/2025q3-derivatives-report)
- Ethena USDe (largest basis-trade vehicle) had ~$7.83B deployable vs ~$65.7B OI (Sep 2025), and by Aug 2026 was expanding into equity perpetuals seeking yield — [BitMEX](https://blog.bitmex.com/2025q3-derivatives-report); [FXStreet Aug 2026](https://www.fxstreet.com/cryptocurrencies/news/ethena-looks-beyond-crypto-to-squeeze-yield-from-booming-equity-perpetuals-202608281313)

### Inferences
- Spot-only alternative: holding a stablecoin in Binance Simple Earn/flexible products captures part of this yield indirectly (with platform/counterparty risk) — not verified in this research.
- Risks: negative funding periods, exchange counterparty risk, liquidation of the short leg on spikes if under-margined, legal access to futures varies by country.

### Gaps
- Could not retrieve 2026 funding-rate averages (DeFiRate snapshot fetch failed). Current Oct 2026 level unverified.

## 6. Regime filters (200-day MA, volatility regime)

### Takeaway
The drawdown benefit of trend/regime filters is the most consistent finding: e.g., TSMOM max drawdown ~62% vs ~89% buy & hold (Han et al.), vol-scaled TSMOM MDD -16% vs BTC -64% in 2022–2024 (Bui & Nguyen, low credibility). Volatility targeting further smooths risk.

### Cited Findings
- Long-only TSMOM invested ~48% of the time, MDD ~62% vs 89%, Sharpe 1.51 vs 0.85 after 15 bps costs — [Han, Kang & Ryu](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)
- Vol-targeting at 25% annualized is core to Zarattini et al.'s design — [CXO](https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/)
- AdaptiveTrend regime table: Bull Sharpe 3.42, Sideways 1.87, Bear -0.31 (trend strategies lose mildly in bears but far less than holding) — [arXiv 2602.11708](https://arxiv.org/html/2602.11708v1)

### Inferences
- A simple "hold only if close > 200-day SMA (or 20–50 week MA), else USDT" filter on BTC/ETH is the most defensible single rule for a tiny account; it trades a handful of times per year.

### Gaps
- No peer-reviewed paper found isolating the 200-day-MA rule specifically on BTC over 2018–2026; practitioner blogs/TradingView scripts found were not rigorous.

## 7. Trading frequency, fees and small accounts (why the ORB bot failed)

### Takeaway
At retail Binance spot fees, round-trip cost is ~0.15–0.30% per trade; strategies trading hundreds of times a year need a gross edge per trade well above that. Intraday crypto edges documented in research are ≤ a few bps gross, so high-frequency retail bots bleed fees. The user's bot paid ~70% of capital in costs.

### Cited Findings
- Binance spot Regular user: 0.100% maker / 0.100% taker; 25% off when paying with BNB → 0.075%/0.075%. VIP 1 requires ≥1,000,000 USD 30-day volume and ≥5 BNB (0.090%/0.100%) — [Binance fee schedule](https://www.binance.com/en/fee/schedule)
- Binance spot API NOTIONAL / MIN_NOTIONAL filters reject orders with price×qty below minNotional (documentation example: 10.00); LOT_SIZE enforces minQty/stepSize — [Binance API filters](https://developers.binance.com/docs/binance-spot-api-docs/filters)
- Short-horizon reversal gross edge ~1.3 bps vs ≥5 bps maker round trip — [arXiv 2608.21888](https://arxiv.org/pdf/2608.21888)
- "No profitable intraday strategies were found for BTCUSD spot" — [Rozario et al.](https://ar5iv.labs.arxiv.org/html/2009.12155)
- Net Sharpe of a 6h trend system falls from 2.87 (0 bps) to 1.62 (12 bps), and H1 bars underperform H4–H8 net — [arXiv 2602.11708](https://arxiv.org/html/2602.11708v1)
- Breakeven costs for daily technical rules typically >50 bps, giving room for daily-frequency strategies — [Hudson & Urquhart](https://link.springer.com/article/10.1007/s10479-019-03357-1)

### Inferences (arithmetic on the user's numbers)
- Round trip in user's backtest = 2×(0.10%+0.05%) = 0.30%. 354 trades × 0.30% ≈ 106% of one position's notional paid in costs over the year. With BNB discount and limit (maker) orders, round trip could drop to ~0.15–0.20%, but that alone would not make a PF 0.24 strategy profitable — the signal itself had negative gross edge (15% win rate).
- ORB on 5m crypto: crypto trades 24/7 so the NY 9:00 "open" has no auction/overnight gap like equities; 15% win rate with tight stops implies stops sized inside normal 5m noise.
- Rule of thumb: required gross edge per trade ≥ 2–3× round-trip cost; at 0.2–0.3% that means targeting moves of ≥0.6–1% net per trade, which pushes toward daily/4h+ timeframes and few trades.
- With 20–40 USD capital and a ~5–10 USDT minimum notional (verify per symbol via exchangeInfo), only 2–4 simultaneous positions are possible; vol-targeted fractional sizing across many coins is not feasible — concentrate on 1–3 assets.

### Gaps
- Exact current minNotional per symbol (commonly 5 USDT for USDT pairs) not verified from an official per-symbol listing; check GET /api/v3/exchangeInfo.

## 8. Overfitting / backtest pitfalls

### Takeaway
With many parameter trials, the best backtest Sharpe is expected to be high by chance; Deflated Sharpe Ratio and Probability of Backtest Overfitting quantify this. Crypto results with few years of data and many rule variants are especially vulnerable.

### Cited Findings
- [PEER] Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", Journal of Portfolio Management 40(5):94-107 (2014): DSR deflates Sharpe for number of trials and non-normal (skewed, fat-tailed) returns — [SSRN 2460551](https://papers.ssrn.com/abstract=2460551)
- [WP/PEER] Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (combinatorially symmetric cross-validation) — [SSRN 2326253](https://papers.ssrn.com/abstract=2326253); R implementation [pbo vignette](https://archive.linux.duke.edu/cran/web/packages/pbo/vignettes/pbo.html)
- Hudson & Urquhart: even after multiple-testing correction, the in-sample-significant rules failed on BTC in the 2018 OOS period — [Springer](https://link.springer.com/article/10.1007/s10479-019-03357-1)
- Han et al.: daily mark-to-market reveals liquidations hidden in weekly data; mean returns unreliable under fat tails; only 3 of 10 "significant" CSMOM portfolios survive with log returns — [AUT PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)

### Inferences
- Practical checklist for the bot: (1) record every variant tried and compute DSR; (2) walk-forward with parameters fixed before each OOS window; (3) prefer ensembles/parameter plateaus over single optimum; (4) include full costs + slippage; (5) require beating buy & hold on risk-adjusted AND drawdown basis; (6) test across 2018 and 2022 bear markets; (7) one 12-month window (~1 regime) is insufficient.

### Gaps
- None critical.

## 9. Concrete simple rule sets with documented (or closely analogous) OOS evidence for a small spot bot

### Takeaway
Candidates ranked by evidence strength, all daily-bar, long-only, USDT as risk-off asset, a few to a few dozen trades/year.

### Cited Findings / rule sets
- A. Donchian ensemble trend (Zarattini et al. 2025, net Sharpe >1.5 on top-20 rotation): per coin, for each N in {5,10,20,30,60,90,150,250,360}: long when close > N-day max close; exit at trailing stop = max(prev stop, midpoint of N-day high/low closes); weight = average of active signals; vol-target ~25% annualized with 90-day stdev; cap at 100% for spot (no leverage) — [CXO](https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/)
- B. Long-only TSMOM (Han, Kang & Ryu): hold coin if trailing 28-day return > 0, re-evaluate every 5 days, else USDT; Sharpe 1.51 net of 15 bps vs 0.85 market, MDD ~62% vs 89% — [AUT PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)
- C. Slow MA crossover (Rozario et al.): ~10-day/40-day SMA crossover on BTC, Sharpe mostly 0.5–1.5 historically, declining recently; costs ignored — [arXiv](https://ar5iv.labs.arxiv.org/html/2009.12155)
- D. DCA baseline (Amdax): weekly buys reduce drawdowns at ~equal Calmar to lump sum — [Medium/Amdax](https://medium.com/amdax-asset-management/lump-sum-or-dollar-cost-averaging-42c8f5bb9938)

### Inferences
- Recommended for 40–300 USD on Binance spot: core = DCA into BTC (+ETH) with a 200-day-MA or 28-day TSMOM regime filter (hold USDT when off); optional satellite = weekly top-1/2 relative-strength rotation among BTC/ETH/SOL/BNB gated by each coin's trend filter. Pay fees in BNB, use limit orders, rebalance weekly or less. Expect lower bull-market returns than buy & hold and much shallower bear drawdowns; benchmark against buy & hold and DCA, not against zero.
- Any 5m/15m strategy should be abandoned unless gross edge per trade demonstrably exceeds ~0.5%.

### Gaps
- None of the rule sets above has an independent, peer-reviewed OOS test on 2024–2026 Binance spot data specifically; the user should run their own walk-forward with DSR before deploying.
