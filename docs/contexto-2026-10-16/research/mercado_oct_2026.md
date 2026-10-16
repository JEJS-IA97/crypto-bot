# Crypto Market State, mid-October 2026 (snapshot dated 2026-10-15/16 UTC)

Anchors from the user's Binance feed on 2026-10-16 UTC: BTC ≈ 82,176; ETH ≈ 2,441; SOL ≈ 105.6; BNB ≈ 729; XRP ≈ 1.335; ADA ≈ 0.230; DOGE ≈ 0.0815; LINK ≈ 12.49 USDT. The independent sources below agree with these to within about 1-3% (for example, Fortune BTC $80,915 at 07:15 ET on Oct 15, and Au79 BTC $81,658 / ETH $2,418 / SOL $104 / XRP $1.33 / LINK $12.41 on Oct 14).

Overall regime call for the report writer: **post-ATH bear market, now in a range-bound partial recovery.** The macro backdrop is hawkish: the Fed is hiking, the 10-year yield is above 5.2%, and oil is above $100. ETF flows are turning negative in October, sentiment has cooled from greed to fear, and leverage is moderate rather than extreme. This argues for reduced aggression, smaller size, and range or mean-reversion logic rather than trend-chasing.

## 1. BTC/ETH price path (last 12 months), drawdown, 200DMA, volatility

### Takeaway
BTC peaked at about $126k on 2025-10-06, then crashed during the record 2025-10-10 liquidation. It bottomed near $60.9k on 2026-06-07, a drawdown of about 51%, and has since recovered to the $80-86k range. As of mid-October 2026 it is about 35% below its ATH and about 27% lower year on year. ETH has done worse, at about 51% below its August 2025 ATH.

### Cited Findings
- BTC ATH $126,198.07 on 2025-10-06. On 2025-10-15 it was $80,915 (07:15 ET). On 2026-10-14 (morning) it was $83,402. A month earlier it was $77,944 (+3.8% m/m). A year earlier it was $110,823 (−27.0% y/y). Market cap is about $1.33T. — [Fortune, Oct 15 2026](https://fortune.com/article/price-of-bitcoin-10-15-2026/)
- On 2026-10-15, ETH was $2,362.73 and XRP $1.30. — [Fortune, Oct 15 2026](https://fortune.com/article/price-of-bitcoin-10-15-2026/)
- Drawdowns from ATH on 2026-10-14: BTC −35.2% from $126,080; ETH −50.9% from $4,946 (Aug 2025); XRP −63% from $3.65 (2025-07-17); AVAX −92.9%. — [Au79 Macro, Oct 14 2026](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity) (single newsletter whose sections contain internal price inconsistencies)
- BTC on the week of Oct 5-9, 2026: opened $85,945, high $86,592 (Oct 6), low $80,652 (Oct 8), about $82,823 by Oct 12 (−3.6% 7d). ETH: opened $2,718, low $2,414, about $2,508 (−7.7% 7d). — [Caleb & Brown weekly rollup, Oct 13 2026](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- On 2025-10-10, over $19B in leveraged positions were liquidated in 24 hours, the largest such day on record. The trigger was Trump's threat of an additional 100% tariff on Chinese imports. BTC fell to about $106.6k, ETH to $3,551 and SOL to $174, and perp OI dropped 43%. — [CCN, Oct 2026](https://www.ccn.com/education/crypto/crypto-october-10-crash-anniversary-2026-liquidation-risk/)
- By the end of 2025, BTC was about 30% below its October 2025 record. — [Fortune](https://fortune.com/article/price-of-bitcoin-10-15-2026/)
- Cycle low of about $60,861 on 2026-06-07, a −51.2% max drawdown that is the mildest of any BTC bear since 2014 (prior drawdowns: −83.6% in 2018, −81.6% in 2015, −76.7% in 2022). On 2026-06-24 the bear had lasted 233 days, BTC was $62,651, and the 200DMA was $76,450, about 22% above spot. In earlier bears, BTC took 65-166 days to go from the bottom back above the 200DMA. — [CoinGecko Research, updated Jun 25 2026](https://www.coingecko.com/research/publications/how-long-do-bitcoin-bear-markets-last). Note a conflict: this page dates the ATH as "$124,773, January 2025", which contradicts Fortune's $126,198 on 2025-10-06. The October 2025 date is corroborated by Fortune, Au79 and CCN, so the CoinGecko date looks like an error.
- BTC was about $64,150 on 2026-06-17. — [The Block, Jun 17 2026](https://www.theblock.co/amp/post/405152/crypto-markets-wobble-hawkish-fed-outlook-kevin-warsh-first-fomc-meeting)
- BTC fell below $60,000 in late June 2026. — [crypto.news, Jul 8 2026](https://crypto.news/40-of-altcoins-near-all-time-lows-as-bitcoin-dominance-stays-high/) (this conflicts slightly with CoinGecko's $60,861 low and may refer to intraday or different venue data)
- In May 2026, BTC was rejected at the 200-day average. — [CoinDesk, May 21 2026](https://www.coindesk.com/markets/2026/05/21/bitcoin-s-rebound-has-a-buyer-problem-as-etf-coinbase-and-korea-demand-fade) (headline only, not fetched)
- On-chain and technical levels cited on 2026-10-14: support $80.3-81k ("cost-basis floor") and $77.2k ("True Market Mean"); resistance $84-86k. For ETH, support is $2,385-2,409 and resistance $2,500-2,530. — [Au79 Macro](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)

### Inferences
- The 200DMA was $76.45k on Jun 24. With BTC having traded mostly between $78k and $86k from roughly mid-September to mid-October, the 200DMA in mid-October is likely in the mid/high-$70ks and BTC is probably modestly **above** it, by an estimated 3-8%. This is not verified. The bot should compute it directly from Binance klines.
- Price action from the June low looks like a bear-market recovery, not a new bull trend. BTC is still 35% below its ATH and repeatedly rejected at $84-86k.
- ETH/BTC is weak (about 0.0297 on Oct 14 per Au79), so ETH is underperforming.

### Gaps
- I could not fetch exact current 200DMA, 50DMA or realized volatility (30d/90d) values. A Binance API call from this environment was blocked (403), and Glassnode DVOL pages are not readable. The bot should compute them from its own Binance data. Realized vol has been elevated, with intraweek swings of about 7% in BTC and about 11% in ETH during Oct 5-9.
- I have no precise monthly closes for Nov 2025 through Sep 2026, so the path between the Oct 2025 ATH and the June 2026 low is not fully documented.

## 2. Macro drivers (Fed, USD, equities, liquidity) and regulation

### Takeaway
The macro backdrop is **hawkish and risk-negative for crypto**. The Fed under Chair Kevin Warsh hiked on 2026-09-16 (its first hike since 2023) to 3.75-4.00%. CPI is re-accelerating (3.7% y/y in September), oil is above $100, and the 10-year yield is at 20-year highs. US equities are nonetheless near record highs, so crypto is lagging stocks. On regulation, the CLARITY Act failed cloture on 2025-09-15 and is stalled until at least the lame-duck session. GENIUS Act rules are late but targeted for November 2026, with an effective date in January 2027.

### Cited Findings
- 2026-06-17: in Warsh's first FOMC meeting as chair, the Fed held at 3.50-3.75% (12-0). Inflation forecasts were raised, crypto fell 1-3%, and the GMCI 30 index was about −36% YTD. — [The Block, Jun 17 2026](https://www.theblock.co/amp/post/405152/crypto-markets-wobble-hawkish-fed-outlook-kevin-warsh-first-fomc-meeting)
- 2026-07-29: the Fed held at 3.50-3.75% in a 9-3 vote, with three dissents for a hike. July CPI was 3.4% y/y, July payrolls were −23k, and unemployment was 4.1%. — [ATFX, Sep 3 2026](https://www.atfx.com/en-au/analysis/financial-events/september-fomc-meeting-2026-is-a-rate-hike-on-the-table)
- 2026-09-16: the Fed hiked to 3.75-4.00%. — [Au79 Macro, Oct 14 2026](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity). The September hike was the first since 2023. The minutes (released Oct 7) showed most officials see another hike as appropriate by year-end, and Gov. Waller said on Oct 8 that he expects more hikes. — [Caleb & Brown, Oct 13 2026](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- Market pricing for the 2026-10-28 FOMC put about a 19-26% chance on a hike, and about 77-85% on a hike by December. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- September CPI (released 2026-10-14) was 3.7% y/y versus 3.6% expected, and core also beat. The 10-year yield was 5.33% (Oct 14), after peaking at about 5.37% on Oct 7, the highest since 2002. The 30-year was 5.56%. DXY was about 102-103. Brent was about $105-107 and WTI about $92-94. Gold was about $4,160-4,216 (its January 2026 peak was about $5,595). — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity); [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- The S&P 500 closed at a record on 2026-10-06 and was at 7,802.79 on Oct 13. UMich sentiment was 46.3 and 1-year inflation expectations 4.7% (preliminary October reading). — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- On 2026-10-07, Brent above $100, the 10-year at 5.28% and DXY at 102.24 coincided with about $404M of long liquidations in one hour. — [CCN](https://www.ccn.com/education/crypto/crypto-october-10-crash-anniversary-2026-liquidation-risk/)
- **CLARITY Act** history: it passed the House in July 2025 and the Senate Banking Committee 15-9 in May 2026. On 2026-06-29, Galaxy put the odds of 2026 passage at 50%, with Polymarket at about 49%. — [Decrypt, Jun 29 2026](https://decrypt.co/372316?amp=1). The Senate cloture vote failed 49-50 on **2026-09-15**, and no new vote is scheduled. House FSC Chair French Hill hopes for lame-duck passage after the Nov 3 midterms. — [Caleb & Brown, Oct 13 2026](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- **GENIUS Act** was signed in July 2025. Agencies missed the July 2026 rulemaking deadline. The OCC is targeting a final rule by November 2026, with an effective date and the start of application processing in January 2027. On 2026-08-19, OCC head Gould said, "What we have is the GENIUS Act," and called CLARITY unlikely this year. — [The Block, Aug 19 2026](https://theblock.co/news/regulation/2026-08-19-occ-races-to-finalize-genius-act-stablecoin-rules-by-november-412240)
- **SEC/CFTC**: the SEC approved six 3x leveraged BTC/ETH ETPs on 2026-10-02, with launch expected late Oct/Nov. — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity). On 2026-10-09, the CFTC proposed treating prediction-market contracts as swaps. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- **EU/MiCA**: ESMA gave EU platforms until 2027-01-08 to wind down exposure to non-MiCA stablecoins such as USDT and PYUSD. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- The US government moved about $1.8B of seized BTC over three days around Oct 8 (including 12,267 BTC from the Bitfinex seizure wallet), with no confirmed sales. It holds about 306,795 BTC per Arkham, and a March 2025 executive order directs forfeited BTC into the Strategic Bitcoin Reserve. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)

### Inferences
- In 2026, rates and oil are the dominant drivers. Hot CPI, rising yields and oil above $100 have each coincided with crypto selloffs. Crypto is underperforming equities that sit near records, which suggests crypto-specific demand is weak.
- Regulatory tailwinds are mostly delayed. The CLARITY Act is unlikely before the lame-duck session at the earliest, so it is not a near-term bullish catalyst, and failure would be a mild negative.

### Gaps
- I did not find a reliable figure for global liquidity or M2.
- The exact December FOMC date is not sourced here. It is probably early-to-mid December 2026, but this needs verification.

## 3. Flows: ETFs, corporate treasuries, stablecoins

### Takeaway
Flows were positive in September 2026 (about $2.6B into BTC ETFs) but **turned negative in October**: BTC ETFs were −$540M month-to-date through Oct 14, and ETH funds had nine straight outflow days. Strategy is still buying, but in small amounts and after having *sold* BTC in August 2026. Stablecoin supply is flat at about $303-307B, which does not signal fresh liquidity.

### Cited Findings
- US spot BTC ETF net flows for October 2026 through Oct 14 were −$539.8M (5 inflow days, 5 outflow days). The largest outflow was −$487.1M on Oct 7. IBIT was about +$245M MTD. — [TFTC ETF tracker](https://www.tftc.io/bitcoin-etf-flows/october-2026)
- In September 2026, about $2.6B flowed into US spot BTC ETFs (about $2.7B in the week of Sep 21) and about $900M into ETH ETFs, per Coinbase Institutional. — [CCN](https://www.ccn.com/education/crypto/crypto-october-10-crash-anniversary-2026-liquidation-risk/)
- In the week to Oct 9, 2026, digital asset products saw over $1.2B in outflows: BTC products −$679M and ETH −$542M (nine-day outflow streak), against XRP +$11.3M, SOL −$25M and HYPE −$9.4M. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- Cumulative BTC ETF net inflows are given as $55.6B-$65.67B. The source is inconsistent here. XRP ETPs have a 13-week inflow streak and $1.8B cumulative. — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- Strategy bought 250 BTC (about $21.5M) and repurchased $192M of STRC preferred around 2026-10-12. — [Strategy press release, Oct 12 2026](https://www.strategy.com/press/strategy-acquires-250-btc-and-repurchases-192-million-of-strc_10-12-2026). It holds 848,250 BTC at an average cost of $75,444. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- Strategy sold 1,638 BTC at $63,957 in August 2026, then bought 1,665 BTC above $79k. Strive holds 35,595 BTC and Metaplanet 44,000 BTC (Q3). — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity) (not cross-verified)
- Robinhood made its first corporate BTC purchase (about $25M). BitMine holds over 6M ETH (about 4.9% of supply) and Tom Lee says it will stop buying at 5%, "99% of the way". — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- On 2026-10-14, total USD stablecoins were $303.4B (−0.56% 7d, +1.4% 90d); DefiLlama showed $306.2B on Oct 12. USDT was $184.1B (60.6% share) and USDC about $72.6B (−1.9% 30d). — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)

### Inferences
- The marginal "structural bid" is fading. BitMine's ETH buying is about to end at its 5% cap, Strategy's buys are small and it has shown willingness to sell, and ETF flows are negative MTD. That removes a support for ETH in particular.
- Flat stablecoin supply suggests no new dry powder entering, which is consistent with range-bound rather than trending conditions.

### Gaps
- I found no verified 2025 full-year or 2026 YTD ETF flow totals, and no ETH ETF October MTD figure.

## 4. Sentiment and positioning

### Takeaway
Sentiment has swung from greed (about 67 in early October) to fear (41 on Oct 14). Funding is close to neutral, and leverage relative to market cap is below pre-crash 2025 levels. However, longs are still being flushed: $771M was liquidated on Oct 12, about 89% of it longs. Leverage is moderate, not euphoric.

### Cited Findings
- Fear & Greed was about 67 ("greed") in early October, 56 around Oct 12 and **41 ("fear") on Oct 14**. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity). For comparison it was about 27 in July 2026. — [crypto.news, Jul 8 2026](https://crypto.news/40-of-altcoins-near-all-time-lows-as-bitcoin-dominance-stays-high/)
- Positioning on 2026-10-14:
  - BTC perps: OI $67.7B (4.13% of market cap), funding +0.0029%/8h.
  - ETH perps: OI $44.8B (15.1% of market cap), funding +0.0045%/8h.
  - SOL: funding 10.9% annualized, with about 70% of accounts long (Oct 10).
  - — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- Liquidations on 2026-10-12 were $771M, 88.9% longs. — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- Positioning versus before the 2025-10-10 crash:
  - BTC OI/market cap is 3.2%, versus 3.7% before the crash.
  - Funding was above 8% annualized on only 1 of 28 observations, versus 18 of 32 before the crash.
  - Coinbase Institutional reports BTC leverage ratio down for four straight months, the lowest since August 2024.
  - Altcoin OI dominance rose to about 1.0 by the end of September.
  - — [CCN](https://www.ccn.com/education/crypto/crypto-october-10-crash-anniversary-2026-liquidation-risk/). Note the conflict: Au79 gives BTC OI/market cap at 4.13% on Oct 14, which may reflect a different methodology or the rise in OI.
- On 2026-10-07, about $404M of longs were liquidated in one hour. — [CCN](https://www.ccn.com/education/crypto/crypto-october-10-crash-anniversary-2026-liquidation-risk/)
- A Ledger reseller compromise (losses of over $86M, unconfirmed) and an Ethereum Foundation warning about quantum risk were also in the news. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)

### Inferences
- Repeated long flushes on macro prints show traders are still buying dips with leverage. Crowded SOL longs are a downside risk.
- Fear at 41 is not capitulation, since readings were in the 20s in mid-2026, so there is no strong contrarian buy signal.

### Gaps
- I did not get the exact alternative.me value for Oct 15/16 or verified CoinGlass totals for 2026 YTD liquidations.

## 5. Sector trends, altseason, BTC dominance

### Takeaway
**This is not an altcoin season.** BTC dominance is about 57.5-59.7%, and many alts are deep below their highs (XRP −63%, AVAX −93%). Around 40% of altcoins were near all-time lows in July 2026. Hyperliquid (HYPE) is the clear 2026 relative winner, with an all-time high in June 2026 while BTC was near its lows. Pockets of rotation appeared in late September and October (the Altseason index reached 61), but they are fragile.

### Cited Findings
- BTC dominance was 57.5-57.6% (CoinGecko) on Oct 14, and 59-59.7% in the Oct 13 rollup. ETH dominance is about 10.4-11.3%. — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity); [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- The Altcoin Season Index was 61 in the week of Oct 13, 2026, versus about 43 in July. About 40% of altcoins were near ATLs in July 2026, rising to 45% when BTC dipped below $60k. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [crypto.news, Jul 8 2026](https://crypto.news/40-of-altcoins-near-all-time-lows-as-bitcoin-dominance-stays-high/)
- HYPE was about $72 on 2026-06-17, one day after setting an all-time high. — [The Block, Jun 17 2026](https://www.theblock.co/amp/post/405152/crypto-markets-wobble-hawkish-fed-outlook-kevin-warsh-first-fomc-meeting). A page ticker showed about $81 (undated). — [crypto.news](https://crypto.news/40-of-altcoins-near-all-time-lows-as-bitcoin-dominance-stays-high/). RWA perps exceeded half of Hyperliquid's weekly volume for the first time. — [ForkLog](https://forklog.com/en/rwa-surpass-half-of-weekly-trading-volume-on-hyperliquid-for-the-first-time/) (headline only)
- XRP: 13 weeks of ETP inflows, but the price is −63% from its July 2025 ATH, −9% in the week to Oct 12, and below its 200DMA ($1.38) on Oct 14. — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity); [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- The total crypto market cap was about $2.81-2.85T in mid-October 2026. Total digital asset products had about $1.2B of outflows in the week to Oct 9, against total market weakness. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- Notable alt moves in the week to Oct 12: TIA +16% (2026 high), KAIA +15.5% (on an Upbit listing), MON −20.5% ahead of a $521M unlock on Nov 24. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- Samsung will enable USDC-on-Solana sends for US Galaxy users from late October 2026. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)

### Inferences
- For a small bot, BTC (and to a lesser extent ETH and SOL) offers the most liquid and least idiosyncratic exposure. Most alts carry structural downtrends and unlock overhangs.
- In this tape, Binance anchor prices for ADA (0.23) and DOGE (0.08) are consistent with deep alt drawdowns.

### Gaps
- I found no reliable 2026 YTD sector-return table covering AI, RWA, memecoins and L2s. The ForkLog sector article I found was from 2024 and is not usable. BNB and SOL YTD performance is not sourced.

## 6. Halving-cycle framing

### Takeaway
The 2025-2026 path broadly rhymes with the 4-year cycle. The halving was in April 2024, the peak in October 2025 (about 18 months later), and a bear market followed, with a provisional low in June 2026 (about 8 months after the peak). This bear was much shallower than past ones (−51% versus −77% to −84%), which supports the view that ETFs and institutions dampen the cycle. Historically, the year after a cycle bottom is a sideways-to-recovery "accumulation" phase.

### Cited Findings
- The current bear is the mildest since 2014 (−51.2%). Prior bear durations were 321-385 days. The June 7, 2026 bottom is unconfirmed. Historically, reclaiming the 200DMA took 65-166 days after the low. The article cites "fading post-halving momentum" as a factor. — [CoinGecko Research, Jun 25 2026](https://www.coingecko.com/research/publications/how-long-do-bitcoin-bear-markets-last)
- Historical bottoms were in Jan 2015, Dec 2018 and Nov 2022. — [CoinGecko](https://www.coingecko.com/research/publications/how-long-do-bitcoin-bear-markets-last)

### Inferences
- Historical precedent:
  - Earlier peaks: Dec 2017, then a bottom in Dec 2018; Nov 2021, then a bottom in Nov 2022. Each bear lasted about 12 months from peak to bottom (general knowledge; not sourced here).
  - An October 2025 peak would therefore imply a late-2026 bottom by analogy. That makes the June 2026 low "early".
  - A retest of the lows into Q4 2026 cannot be ruled out, especially with a hiking Fed. Only three to four prior cycles exist, so the sample is tiny.
- The halving dates (April 2024, and the next one expected around 2028) are general knowledge and not sourced in these notes.

### Gaps
- I found no quality 2026 cycle-debate source (Glassnode or CryptoQuant), and no MVRV or realized-price figures beyond the Au79 "True Market Mean" of $77.2k.

## 7. Upcoming catalysts (late 2026)

### Cited Findings
- 2026-10-16: settlement of BTC options and prediction markets around the $83,000-83,500 strikes. Thailand spot BTC/ETH ETF rules take effect. — [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity); [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- 2026-10-19: China Q3 GDP. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- **2026-10-28: FOMC decision.** About 19-26% odds of a hike; about 77-85% odds of a hike by December. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- Late October: Samsung USDC/Solana rollout. Late Oct/Nov: launch of six 3x leveraged BTC/ETH ETPs. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/); [Au79](https://martyau79.substack.com/p/14oct2026-crypto-and-macro-liquidity)
- **2026-11-03: US midterms.** A lame-duck window for the CLARITY Act follows. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- November 2026: OCC final GENIUS Act rule targeted. — [The Block](https://theblock.co/news/regulation/2026-08-19-occ-races-to-finalize-genius-act-stablecoin-rules-by-november-412240)
- 2026-11-24: Monad (MON) unlock of about $521M. — [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)
- January 2027: GENIUS Act effective date. 2027-01-08: ESMA deadline for non-MiCA stablecoins. — [The Block](https://theblock.co/news/regulation/2026-08-19-occ-races-to-finalize-genius-act-stablecoin-rules-by-november-412240); [Caleb & Brown](https://calebandbrown.com/blog/weekly-rollup-october-13-2026/)

### Inferences — implications for the bot's aggressiveness
- Overall risk posture: **defensive to neutral**. That means roughly half or less of normal position size and lower or no leverage, with wider stops calibrated to the elevated volatility.
- Favor mean-reversion in BTC's $78-86k range, and avoid chasing breakouts until there is a daily close above about $86k accompanied by positive ETF flows.
- Blackout or size-reduce windows: US CPI and PPI prints, the 2026-10-28 FOMC, and the Nov 3 midterms.
- Avoid low-liquidity alts and tokens with near-term unlocks. Watch SOL long crowding.
- Regime switches to monitor:
  - A daily close below about $77-80k, combined with rising yields or oil, would point to a risk of retesting $60-65k.
  - Reclaiming $86k, with ETF inflows and Fear & Greed recovering, would point to a resumed recovery.

### Gaps
- The December FOMC date, Q4 2026 token unlocks beyond MON, and pending SEC altcoin ETF decisions with specific deadlines were not sourced.
