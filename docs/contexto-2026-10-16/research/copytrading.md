# Crypto Copy Trading 2025-2026: Follower Outcomes, Lead-Trader Selection, Exchanges/APIs, Venezuela Availability

Scope note: This research was done on 2026-10-15. Many exchange-feature facts come from third-party summaries, because official help pages were often dynamic and could not be fetched. Anything marked "UNVERIFIED" comes from my prior knowledge and was not confirmed by a source fetched in this session.

## 1. Evidence on follower profitability (studies, data, biases, fees, slippage)

### Takeaway
The evidence does not show that copy trading reliably makes money for followers. Lab evidence shows copying pushes people into more risk than they would choose for themselves. Field evidence shows losses on copied trades are larger in bad periods. Recent crypto-specific data shows about half of followers, or fewer, end up profitable. Even then, 97% of lead traders are profitable themselves, so a profitable leader does not mean profitable followers. On top of that, fees (10-30% profit share), slippage and survivorship bias in the leaderboards lower what followers actually get.

### Cited Findings
- **Apesteguia, Oechssler & Weidenholzer, "Copy Trading"** (lab experiment; BSE Working Paper No. 1048, later published in *Management Science*, 2020 per Wikipedia's citation):
  - Seeing other traders' choices made participants take more risk.
  - About one-third chose to copy someone, and most copied the traders who had picked the riskiest assets, which sharply raised risk-taking.
  - The authors conclude that copy trading lowered traders' ex-ante welfare.
  - It is a lab study. The authors expect similar effects on eToro, ZuluTrade and Tradeo but did not test them.
  - Sources: [BSE Focus](https://dev.focus.bse.eu/copy-trading-risk-taking/); [Wikipedia: Copy trading](https://en.wikipedia.org/wiki/Copy_trading)
- **Pelster & Hofmann (2018, *Journal of Banking & Finance*):** When returns were negative, losses on copied trades were usually larger. Traders who were copied were more prone to the disposition effect. — [Wikipedia summary](https://en.wikipedia.org/wiki/Copy_trading)
- **Liu et al. (2014, PLOS ONE):** Copied trades were more likely to be profitable, but returns on profitable copied trades were lower than on profitable regular trades. — [Wikipedia summary](https://en.wikipedia.org/wiki/Copy_trading)
- **Doering, Neumann & Paul (2015):** The traders people followed were often, but not consistently, the best performers. — [Wikipedia summary](https://en.wikipedia.org/wiki/Copy_trading)
- **Pan, Altshuler & Pentland (2012, eToro-type data):** Copying a suggested investor did about 6-10% better than trading manually, and about 4% better than copying a randomly chosen investor. This is an older, pre-crypto study of a social FX platform. — [Wikipedia summary](https://en.wikipedia.org/wiki/Copy_trading); see also [arXiv 1406.7729](https://arxiv.org/pdf/1406.7729)
- **"YieldFund Multi-Exchange Study, 2025"** (90 days, 100,000+ outcomes), as cited by KuCoin's blog:

  | Exchange | Follower win rate | Net follower PnL | Leaders with positive follower returns |
  |---|---|---|---|
  | Binance | 66.5% | +572,979 USDT | 72.45% |
  | Bybit | 43.65% | +346,106 USDT | 40.34% |
  | MEXC | 57.79% | -210,040 USDT | below 50% |
  | Blended | 48.48% | — | 43.61% |

  - The same page says 97% of lead traders had positive personal PnL.
  - Caveats: the blended win rate's method is not explained. The primary study was not found; this is a secondary citation on an exchange's marketing blog.
  - Source: [KuCoin blog, "Is Crypto Copytrading Profitable in 2026?"](https://www.kucoin.com/blog/is-crypto-copytrading-profitable-in-2026)
- **On-chain "social trading" (DWF Ventures research on the Fomo app, reported 2026-08-28):**
  - 292,000 wallets over 3 months; only 6.16% were in profit (realized gains), so about 94% lost.
  - Only 25 winning wallets cleared $10k net.
  - DWF attributes this to market structure: callers profit when followers buy in, and followers absorb the losses when callers exit.
  - Source: [Yellow.com](https://yellow.com/news/fomo-copy-trading-94-percent-wallet-losses)
- **Fees:**
  - Profit sharing is typically 10-30% of profits. KuCoin lead traders can take up to 30%. — [KuCoin blog](https://www.kucoin.com/blog/is-crypto-copytrading-profitable-in-2026)
  - Binance spot copy trading: lead traders get 10% of followers' profits plus 10% of the trading fees copiers pay. Binance charges spot copiers no extra fee. — [CoinBureau review (Dec 2024)](https://coinbureau.com/review/binance-copy-trading-review)
  - The KuCoin blog's own unsourced estimate is that headline returns can be 30-50% lower after costs.
- **Slippage and latency:**
  - Bybit lets followers set a maximum slippage per order (example: 1.8% from the leader's entry). Trades outside that limit are not copied.
  - Bybit's "Copyguard" can skip trades with a worse entry price.
  - Exit equity can differ from what is displayed because of slippage.
  - Source: [Bybit Copy Trading Classic FAQ](https://www.bybit.com/kk-KZ/help-center/article/FAQ-Copy-Trading)

### Inferences
- **Leader stats overstate what followers earn.** If 97% of leaders are profitable but only about 40-72% of leaders produce positive follower returns, the gap is execution (later entries, slippage, different sizing) plus fees. Selecting on the leader's own ROI is not enough. Where the platform shows follower PnL ("copier PnL"), select on that instead.
- **Platform matters.** Follower outcomes differed a lot between Binance and MEXC/Bybit in the same study. Exchange choice is itself a risk factor.
- **Small accounts are disadvantaged.** With tens of USD, fixed per-order minimums (for example, 10 USDT per order on Bybit for a Bronze master) force either large position sizes relative to equity or many failed copies.
- **Survivorship bias.** Leaderboards only show traders currently alive and ranked. Leaders who blew up, and the copiers who lost with them, disappear from view. No study quantifying this for crypto exchanges was found.

### Gaps
- No peer-reviewed 2025-2026 study of follower outcomes on Binance, OKX, Bybit or Bitget was found. The "YieldFund" study could not be located as a primary source.
- No exchange-published aggregate follower-PnL data was found for 2025-2026.
- No quantified survivorship-bias study for crypto copy trading was found.
- No eToro-published follower-outcome research for 2025-2026 was retrieved.

## 2. Exchanges: copy trading features (spot vs futures) and APIs usable by a bot

### Takeaway
OKX is the clear best fit for a bot. It has documented **public** endpoints to rank lead traders and pull their stats, PnL and positions, and **authenticated follower** endpoints to start, amend and stop copying (futures/SWAP). Bitget documents follower endpoints in its copy-trading API. Binance's official copy-trading API only covers lead-trader status and symbols, not following. Bybit and BingX do not appear to expose a usable follower API (not fully verified).

### Cited Findings
- **OKX** (API v5)
  - Public, no-auth endpoints:
    - `GET /api/v5/copytrading/public-lead-traders` (lead trader ranks)
    - `public-stats`, `public-pnl` (daily), `public-weekly-pnl`
    - `public-preference-currency`, `public-current-subpositions`, `public-subpositions-history`
    - `public-copy-traders`, `public-config`
  - Follower, auth-required endpoints:
    - `POST /api/v5/copytrading/first-copy-settings` (start copying)
    - `POST .../amend-copy-settings`
    - `POST .../stop-copy-trading`, with `subPosCloseType` set to `market_close`, `copy_close` or `manual_close`
    - `GET .../copy-settings`, `current-lead-traders`, `lead-traders-history`
    - `batch-set-leverage`, `close-subposition`, `algo-order`
  - Example start-copy parameters: `instType: SWAP`, `uniqueCode` (the leader's code), `copyMode: fixed_amount`, `fixedAmt`, `copyMgnMode`, `instIds`.
  - Source: [tiagosiebler okx-api docs (mintlify mirror)](https://mintlify.wiki/tiagosiebler/okx-api/rest-client/copy-trading); [qveris endpoint listing](https://qveris.ai/tools/okx_api_v5.copytrading.public-lead-traders.list.v5.2bfcea0c)
- **Binance**
  - The official copy-trading API section documents only two endpoints:
    - `GET /sapi/v1/copyTrading/futures/userStatus` (is the user a lead trader)
    - `GET /sapi/v1/copyTrading/futures/leadSymbol` (symbol whitelist)
  - There are no follower endpoints to follow or list traders. — [Binance Developers: Copy Trading](https://developers.binance.com/docs/copy_trading/future-copy-trading)
  - Binance launched futures copy trading in 2023 and spot copy trading in 2024. — [The Block (futures)](https://www.theblock.co/post/255396/binance-introduces-copy-trading-feature-for-futures-markets); [The Block (spot)](https://www.theblock.co/post/290345/binance-spot-copy-trading)
  - Copy modes are Fixed Ratio and Fixed Amount. Followers can set a total stop loss, cost per order and a pair preference. Lead traders need more than 500 USDT and KYC. — [CoinBureau](https://coinbureau.com/review/binance-copy-trading-review)
  - Unofficial leaderboard scrapers exist, for example [rtunazzz/bfldb](https://github.com/rtunazzz/bfldb). They rely on undocumented endpoints and are fragile.
- **Bybit (Copy Trading Classic)**
  - Markets: USDT perpetuals (plus TradFi perps).
  - Followers can copy up to 10 master traders.
  - The minimum fixed margin per trade depends on the master's rank (example: 10 USDT for Bronze). Maximum fixed margin per trade: Cadet 1,000, Bronze 2,000, Silver 10,000 USDT.
  - Requires KYC Lv.1. Bonuses and coupons cannot be used. Sub-accounts are supported.
  - Followers are auto-unfollowed after 20 consecutive failed copies, or 100 failed copies in 24 hours.
  - The FAQ links to API docs for Copy Trading Classic but does not say followers can copy via API.
  - Source: [Bybit FAQ](https://www.bybit.com/kk-KZ/help-center/article/FAQ-Copy-Trading)
  - UNVERIFIED (prior knowledge): Bybit's V5 API copy-trading support is for master traders placing orders, not followers subscribing.
- **Bitget**
  - The API docs include a "future-copytrade / follower" section, for example "Get Copy Trade Settings". — [Bitget API doc](https://www.bitget.com/api-doc/copytrading/future-copytrade/follower/Query-Settings)
  - UNVERIFIED (prior knowledge, could not render the pages): v2 paths such as `/api/v2/copy/mix-follower/query-traders`, `settings`, `cancel-trader`, plus spot-follower equivalents.
  - Bitget offers both futures and spot copy trading. — [Bitget academy/support](https://www.bitget.com/support/articles/12560603800577)
  - Bitget hack (single unconfirmed source): Datawallet reports hackers drained Bitget hot/warm wallets on 24 Sept 2026, with fiat/P2P frozen and restored about 2 Oct. — [Datawallet](https://www.datawallet.com/es/cripto/best-crypto-exchanges-venezuela)
- **BingX**
  - Copy Trading 2.0 (June 2025) is perpetual futures only. Each follower gets a separate sub-account, and the leader's leverage and margin mode are mirrored. — [HackerNoon press release](https://www.hackernoon.com/bingx-introduces-copy-trading-20-greater-control-transparency-and-flexibility)
  - BingX has also expanded copy trading to spot. — [The Paypers](https://thepaypers.com/crypto-web3-and-cbdc/news/bingx-expands-copy-trading-to-the-spot-market)
  - No follower API was found.
- **KuCoin**
  - Copy trading with up to 30% profit share; "TraderPro" funded accounts of up to 5,000 USDT for leaders. — [KuCoin blog](https://www.kucoin.com/blog/is-crypto-copytrading-profitable-in-2026)

### Inferences
- **Recommended bot architecture on OKX:**
  1. Poll `public-lead-traders`, then for each candidate pull `public-stats`, `public-pnl` and `public-subpositions-history` to compute metrics.
  2. Start following with `first-copy-settings`, using `fixed_amount` with a small amount and explicitly capped leverage via `batch-set-leverage`.
  3. Exit with `stop-copy-trading` when risk triggers fire.
- **Binance or Bybit for automation.** The likely path is "manual follow in the app" plus a bot that monitors the leaderboard (scraped data, fragile) and the account's own positions through standard trading APIs. Alternatively, a self-built "shadow copy": read the leader's public positions and replicate them through the normal trade API. That adds latency and slippage.
- **Size limits.** Minimum per-order sizes (about 10 USDT) plus a 10-30% profit share mean a 50-200 USD account can realistically follow only 1-3 leaders.

### Gaps
- Official OKX docs page not fetched directly. The endpoint list is from a well-maintained SDK mirror and should be cross-checked at okx.com/docs-v5 (Copy Trading section).
- The exact list of Bitget v2 follower endpoint paths could not be confirmed (pages did not render).
- Not confirmed whether Bybit or BingX offer follower APIs.
- Not confirmed whether OKX copy trading covers spot through the API. The examples are SWAP; OKX does have spot copy trading in-app (UNVERIFIED).
- Current per-exchange follower minimums and profit-share ranges for 2026 were not confirmed from official pages.

## 3. Lead-trader selection criteria and red flags

### Takeaway
No source validates a selection rule out-of-sample. The defensible approach combines track record length, drawdown, leverage, consistency and follower PnL, and avoids the riskiest top-ROI traders. The academic evidence suggests copiers chase exactly those risk-takers, and that luck explains much of their outperformance.

### Cited Findings
- **Copiers gravitate to the riskiest traders.** Most copiers chose traders who had picked the riskiest assets. — [BSE Focus](https://dev.focus.bse.eu/copy-trading-risk-taking/)
- **Luck and risk under large payoffs.** Under large payoffs, imitation leads toward risky decisions, so "efficient" investors may simply be lucky and risk-loving (Offerman & Schotter 2009). — [Wikipedia](https://en.wikipedia.org/wiki/Copy_trading)
- **Disposition effect in copied traders.** Copied traders show more of the disposition effect (holding losers), consistent with "no stop-loss" patterns. — [Wikipedia (Pelster & Hofmann 2018)](https://en.wikipedia.org/wiki/Copy_trading)
- **KuCoin's screening framework** (not evidence-based; author's own framework):
  - Max drawdown under 20%
  - Win rate 55-65%
  - Profit factor above 1.5
  - Avoid putting 80%+ of capital with one trader
  - Source: [KuCoin blog](https://www.kucoin.com/blog/is-crypto-copytrading-profitable-in-2026)
- **Hyperliquid vault example of blow-up dynamics.** One vault ("Follow the Money") showed:
  - −51% over 3 months, max drawdown −61.7%, Sharpe −2.2, 102.7% volatility
  - Down more than 95% from peak, TVL now 0
  - 10% performance fee
  - It illustrates how quickly a public strategy can collapse. — [tradingstrategy.ai](https://tradingstrategy.ai/vaults/follow-the-money)
- **OKX data available for a bot.** OKX public endpoints expose per-leader stats, daily and weekly PnL, current and historical sub-positions (including leverage) and copier lists. These are enough to compute drawdown, a leverage history and trade-level metrics. — [okx-api docs](https://mintlify.wiki/tiagosiebler/okx-api/rest-client/copy-trading)

### Inferences
**Proposed bot filter.** These are reasoned thresholds, not empirically validated.

- Track record of at least 180 days (ideally more than 1 year, spanning at least one major drawdown in BTC).
- Max drawdown of at most 20-25%.
- Return divided by max drawdown of at least 2.
- Median leverage of at most 5-10x, with no sudden leverage spikes (for example, max leverage more than 2x the 90-day median).
- More than 100 closed trades.
- Positive **copier PnL** as well as positive leader PnL.
- Stable AUM: prefer moderate AUM, since a very large AUM worsens slippage for followers.
- Stable monthly returns: low standard deviation, more than 60% positive months.

**Red flags to hard-reject:**

- Martingale or grid averaging-down: position size grows after losses, with many adds per position.
- Very high win rate (more than 90%) with a few huge losses. This signals no stop-loss and holding losers.
- Long-held losing positions with large unrealized losses.
- Leverage jumps.
- Short history with outsized ROI.
- A sudden increase in trade frequency after a drawdown, which suggests revenge trading.

**Monitoring triggers (auto stop-copy):**

- Account-level stop: equity loss of 15-20% from the follow start.
- Leader drawdown exceeds its historical max by 1.25x.
- Leverage exceeds the cap.
- Leader goes inactive.
- Copier PnL turns negative over 30 days.

**Diversification.** Split across 2-3 uncorrelated leaders only if the minimums allow it.

### Gaps
- No empirical study was found that tests which crypto lead-trader metrics predict future follower returns.
- No exchange-published data on lead-trader churn or blow-up rates was found.

## 4. Exchange availability for Venezuela residents, sanctions and KYC (as of Oct 2026)

### Takeaway
None of the major exchanges reviewed appears to list Venezuela as a fully restricted jurisdiction. Bybit, Binance and OKX are actively used there, with bolívar P2P markets. The real risks are:

- Government blocking. Venezuela DNS-blocked Binance in August 2024.
- The lack of any local license.
- Targeted (not comprehensive) US sanctions, which matter mainly if the user is linked to the government or PDVSA, or is on the SDN list.

### Cited Findings
- **Datawallet ranking for Venezuela** (updated 27 Sep 2026; tests run 25 Sep 2026):
  1. Bybit: P2P with Pago Móvil, Banesco, Mercantil, Provincial and some Zelle. KYC with cédula or passport plus facial verification.
  2. Binance: P2P added Banco de Venezuela, Banco del Tesoro and BDT on 15 Apr 2026.
  3. OKX: P2P with Pago Móvil; KYC can take days.
  4. KuCoin
  5. (not named in the summary)
  6. Bitget: affected by the 24 Sep hack.
  - None of the six holds a Venezuelan (SUNACRIP) license; only Crixto and Kontigo do.
  - Bybit and Binance approved the test KYC accounts in under 2 hours.
  - Source: [Datawallet](https://www.datawallet.com/es/cripto/best-crypto-exchanges-venezuela)
- **Venezuela blocked Binance in August 2024.** The website and app were DNS-blocked around 9 Aug 2024, after the election, by government order via Conatel. VE sin Filtro recommended VPNs. — [ForkLog](https://forklog.com/en/venezuela-blocks-access-to-binance-social-network-x-and-other-services/)
  - Datawallet also notes "El gobierno de Venezuela restringió el acceso a Binance en agosto de 2024." — [Datawallet](https://www.datawallet.com/es/cripto/best-crypto-exchanges-venezuela)
- **Binance removed Banco de Venezuela from P2P in August 2023**, citing international compliance. — [Forbes Argentina](https://www.forbesargentina.com/money/binance-endurece-sus-medidas-control-evitar-conflictos-rusia-venezuela-n39968)
  - Banco de Venezuela was re-added in April 2026, per [Datawallet](https://www.datawallet.com/es/cripto/best-crypto-exchanges-venezuela).
- **Binance restricted list.** The fully restricted list cited by Datawallet covers Iran, North Korea, Syria, Cuba, occupied regions of Ukraine, the US, Canada, the Netherlands, Russia, UK new registrations and the EU (MiCA, July 2026). Venezuela is not listed. Venezuela was about 4.55% of binance.com traffic. — [Datawallet Binance countries](https://www.datawallet.com/es/cripto/pa%C3%ADses-con-restricciones-binance)
- **OKX restricted list** (per Datawallet): Afghanistan, Cuba, Iran, North Korea, Syria, Crimea/Donetsk/Luhansk, Canada, Hong Kong, India, Japan, Malaysia, Uzbekistan, Nepal and US territories. Venezuela is not listed. — [Datawallet OKX](https://www.datawallet.com/es/cripto/okx-pa%C3%ADses-restringidos)
- **US sanctions in 2026 are targeted, not comprehensive.**
  - Restrictions focus on the Government of Venezuela, PdVSA and SDNs.
  - GL 57 (14 Apr 2026) authorizes financial-services transactions with Banco Central de Venezuela, Banco de Venezuela, Banco Digital de los Trabajadores and Banco del Tesoro, including digital wallets. It excludes SDNs.
  - GL 60 (earthquake relief) runs to 23 Oct 2026.
  - No authorities have been revoked, so OFAC could reverse course.
  - Source: [Faegre Drinker, 23 Jul 2026](https://www.faegredrinker.com/zh/insights/publications/2026/7/update-additional-changes-to-the-venezuela-sanctions-program-impacting-the-energy-minerals-financial-services-and-aviation-sectors); also [Foley, Aug 2026](https://www.foley.com/insights/publications/2026/08/ofac-reaffirms-recent-licenses-along-with-new-license-in-response-to-venezuela-earthquakes/)

### Inferences
- An ordinary Venezuelan resident (not a government official and not on the SDN list) can most likely complete KYC and use copy trading on Bybit, Binance, OKX and Bitget.
- **OKX is the most bot-friendly choice** but has slower KYC and thinner P2P.
- **Bybit has the best local P2P** but probably no follower API.
- Risk of a government DNS block: a bot running on a VPS outside Venezuela reduces the risk of API access being cut.
- Using a VPN to evade an exchange's own geo-restrictions could breach its terms. That is different from evading a local ISP block.
- **Avoid Bitget** until its post-hack status is clear.

### Gaps
- Official restricted-country pages (Binance Terms, OKX Risk & Compliance Disclosure, Bybit, Bitget, BingX) were not fetched directly. Venezuela's status relies on third-party summaries and should be verified on the official pages.
- BingX's availability in Venezuela was not covered by any source found.
- Not confirmed whether copy trading specifically (as opposed to spot) is restricted for any region in 2026.
- Whether Binance is still DNS-blocked in Venezuela in Oct 2026 is unknown. The Apr 2026 P2P bank additions suggest normalization, but this is unconfirmed.

## 5. Alternatives: on-chain wallet mirroring, Hyperliquid vaults, public strategies

### Takeaway
On-chain copying has the weakest evidence so far: about 94% of wallets lost money on a social trading app in 2026, and callers are structurally incentivized to profit from their followers. Hyperliquid vaults give transparent on-chain track records and a 10% performance fee. Individual vaults can still collapse, and no aggregate depositor-return study was found.

### Cited Findings
- **DWF Ventures on Fomo:** 292k wallets over 3 months; 6.16% profitable; callers profit from followers' entries. — [Yellow.com](https://yellow.com/news/fomo-copy-trading-94-percent-wallet-losses)
- **Hyperliquid vault example:** a 10% performance fee and no other fees, yet a −61.7% max drawdown, deposits closed and TVL at 0. Displayed PnL excludes deposit and redemption flows, so it is not the depositor's actual return. — [tradingstrategy.ai](https://tradingstrategy.ai/vaults/follow-the-money)
- **New-generation Hyperliquid vaults (HyperEVM)** can use spot and HIP-3 and have customizable accounting (EIP-4626). Legacy 2023 HyperCore vaults do not support spot or HIP-3. — [Hyperliquid docs](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/vaults)
- UNVERIFIED (prior knowledge) on legacy HyperCore vaults:
  - The leader must keep at least 5% of the vault.
  - The leader earns a 10% profit share.
  - Depositors face a 1-day lockup (the HLP has a 4-day lockup).
  - Vault details are queryable via the Hyperliquid info API (`vaultDetails`).
- **Third-party vault analytics** (APY, drawdown, Sharpe) exist for Hyperliquid vaults. — [tradingstrategy.ai](https://tradingstrategy.ai/vaults/follow-the-money)

### Inferences
- Hyperliquid vaults suit a bot well: fully on-chain and transparent, with no KYC. The same selection filters from Section 3 apply.
- Hyperliquid's own vault rules are covered only by unverified prior knowledge (above); its geo-access policy for Venezuela was not checked. The user must also manage bridging and self-custody risk.
- Mirroring memecoin or "caller" wallets is adversarial: the leader can exit into followers' buys. It is not suitable for a capital-preservation goal.

### Gaps
- No aggregate study of Hyperliquid vault depositor returns or survivorship was found.
- No evidence was found on the performance of "mirror whale/smart-money wallet" strategies (Nansen, Arkham and similar tools) beyond the DWF/Fomo data.
- No source was found on Hyperliquid's geo-restrictions or terms regarding Venezuela.
