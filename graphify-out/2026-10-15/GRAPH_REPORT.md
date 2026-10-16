# Graph Report - crypto-bot  (2026-10-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3826 nodes · 9980 edges · 199 communities (145 shown, 54 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 836 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9b119dce`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Base
- json
- ._analyze
- SignalDecision
- DecisionStatus
- TradeSide
- scripts/core.py
- ShadcnInstaller
- external_signal_service.py
- create_hypothesis
- bot_loop.py
- test_circuit_breaker.py
- gray
- Settings
- design_system.py
- strategy_lab_service.py
- test_orb_engine.py
- report_service.py
- bot.js
- validate_data.py
- simulation.py
- SimulationAccountCreate
- BinanceSpotClient
- BinanceExecutor
- ._evaluate
- OrbConfig
- test_portfolio_math.py
- Simulation.jsx
- shutil
- test_keepalive_service.py
- OKXDemoClient
- market_context_service.py
- bot_engine.py
- test_core.py
- replay_service.py
- Candle
- test_market_context.py
- BinanceMarketDataClient
- package.json
- react
- html-token-validator.py
- send_email
- backtest_orb
- ai_advisor_service.py
- test_data_contracts.py
- test_strategy_lab.py
- test_workflows.py
- logo/generate.py
- DesignSystemGenerator
- test_core_data_quality.py
- AiEvaluation
- observability.js
- pathlib
- FakeMarketData
- csv
- client.js
- DepthBook
- ._nodes
- candidate_service.py
- bot_runner_service.py
- re
- generate-slide.py
- object
- spacing
- TestTailwindConfigGenerator
- SignalAction
- _select_palette_for_mode
- read_rows
- _handle_signal
- .from_json
- OrderRejectedError
- MarketDataUnavailable
- risk_engine_service.py
- fetch-background.py
- slide_search_core.py
- TailwindConfigGenerator
- collect_klines.py
- color
- EventsEndpointTests
- test_risk_capitals.py
- actionSystem.test.js
- main
- TestWebStackFreshness
- OrderRequest
- cip/generate.py
- httpx
- FakeMarketData
- fontSize
- test_native_desktop_stack_freshness.py
- ReplayApiBase
- extract-colors.cjs
- CatalogRefreshTest
- score_candidate
- _capture
- devDependencies
- Simulation.test.jsx
- sync-brand-to-tokens.cjs
- validate-asset.cjs
- radius
- test_style_taxonomy.py
- read_candidates
- compute_features
- test_feature_engine.py
- CandidatesApiBase
- logo/core.py
- vitest
- design-tokens-starter.json
- TestDomainDetection
- test_text_layout_resilience.py
- argparse
- DailyPassTests
- embed-tokens.cjs
- validate-tokens.cjs
- card
- _style_is_dark_primary
- render-html.py
- _session_factory
- WhyApiBase
- inject-brand-context.cjs
- search-slides.py
- generate-tokens.cjs
- button
- duration
- arbitrage_service.py
- test_ai_isolation.py
- AiStatsApiBase
- ExecutionModeTests
- BM25
- BM25
- test_validate_tokens.py
- cip/search.py
- BotLoopController
- _render_html
- RiskAction
- Session
- configure_logging
- ChunkDownloadAndResumeTests
- CredentialsGuardTests
- DuplicateAndSymbolTests
- StrategyVersionTests
- generate_logo
- input
- logo/search.py
- candidate_engine.py
- run_daily_pass
- hashlib
- _filter_anti_patterns_for_mode
- TestThresholdGate
- test_skill_script_paths.py
- select_best_execution
- market_sync_service.py
- _num
- EventPersistenceTests
- ExposureEndpointTests
- CatalogSummaryLineEndingsTest
- TestGeneratedCatalogContract
- scripts/search.py
- halved_share
- find_best_opportunity
- ForeignKeyTests
- LifespanBotStartTests
- RetentionTests
- $type
- radius
- lg
- sm
- TestMetricMath
- risk_exposure
- RedactionTests
- IsolationTests
- CliConfigGuardTests
- _load_csv
- padding-y
- xl
- none
- TestFixtureValidation
- .test_api_responsive_during_loop
- DialectGuardTests
- EngineOptionsTests
- _LoggedRecord
- 16
- 1
- 3
- 8
- destructive
- destructive-foreground
- muted
- primary-foreground
- ring
- secondary-foreground

## God Nodes (most connected - your core abstractions)
1. `SignalDecision` - 100 edges
2. `Candle` - 98 edges
3. `Base` - 94 edges
4. `TradeSide` - 71 edges
5. `DecisionStatus` - 70 edges
6. `PositionV2` - 69 edges
7. `_enable_sqlite_foreign_keys()` - 65 edges
8. `utc_now()` - 65 edges
9. `TailwindConfigGenerator` - 60 edges
10. `SimulationAccountCreate` - 55 edges

## Surprising Connections (you probably didn't know these)
- `lifespan()` --uses--> `Base`  [INFERRED]
  backend/app/main.py → backend/app/database.py
- `main()` --uses--> `Base`  [INFERRED]
  backend/send_daily_report.py → backend/app/database.py
- `AdvisorBase` --uses--> `Base`  [INFERRED]
  backend/tests/test_ai_advisor_service.py → backend/app/database.py
- `AiApiBase` --uses--> `Base`  [INFERRED]
  backend/tests/test_ai_api.py → backend/app/database.py
- `DailyPassBase` --uses--> `Base`  [INFERRED]
  backend/tests/test_ai_daily.py → backend/app/database.py

## Import Cycles
- None detected.

## Communities (199 total, 54 thin omitted)

### Community 0 - "Base"
Cohesion: 0.07
Nodes (19): Base, _enable_sqlite_foreign_keys(), _engine_options(), Hypothesis, SimulationAccount, SimulationArbitrage, SimulationBalance, list_hypotheses() (+11 more)

### Community 1 - "json"
Cohesion: 0.06
Nodes (28): clamp_limit(), _event_payload(), list_events(), list_sources(), observability_metrics(), pipeline_nodes(), lifespan(), SourceHealth (+20 more)

### Community 2 - "._analyze"
Cohesion: 0.06
Nodes (15): _extract_text(), GeminiClient, GeminiQuotaExceeded, GeminiReply, GeminiUnavailable, AdvisorBase, CacheBreakerTests, ConfigStateTests (+7 more)

### Community 3 - "SignalDecision"
Cohesion: 0.06
Nodes (22): require_control_token(), bot_metrics(), bot_status(), change_bot_phase(), get_bot_phase(), start_bot(), stop_bot(), health_check() (+14 more)

### Community 4 - "DecisionStatus"
Cohesion: 0.05
Nodes (21): DailyRiskState, DecisionOrigin, DecisionStatus, HypothesisStatus, SimulationMarketPrice, _decision_correlation(), get_metrics(), has_technical_decision_since() (+13 more)

### Community 5 - "TradeSide"
Cohesion: 0.08
Nodes (30): PositionStatus, PositionV2, SimulationPosition, SimulationTrade, TradeIncident, TradeSide, SimulationOrderRequest, check_exits() (+22 more)

### Community 6 - "scripts/core.py"
Cohesion: 0.06
Nodes (31): BM25, _contains_phrase(), detect_domain(), _domain_keywords(), _exact_match_diagnostic(), _exact_row_identity(), _exact_stack_identifier(), _file_signature() (+23 more)

### Community 7 - "ShadcnInstaller"
Cohesion: 0.06
Nodes (3): main(), ShadcnInstaller, TestShadcnInstaller

### Community 8 - "external_signal_service.py"
Cohesion: 0.06
Nodes (23): calculate_order_size(), can_open_position(), _ceil_to_step(), estimated_loss_usd(), _floor_to_step(), _require_decimal(), SizingResult, stop_take_prices() (+15 more)

### Community 9 - "create_hypothesis"
Cohesion: 0.07
Nodes (10): create_hypothesis(), _json_text(), _parse_dt(), transition_hypothesis(), LearningApiBase, LearningAuthTests, LearningEndpointsTests, EvaluateHypothesisTests (+2 more)

### Community 10 - "bot_loop.py"
Cohesion: 0.08
Nodes (17): SymbolRules, _current_mode(), CycleReport, _execute_cycle(), _is_running(), _mark_external_closed(), _mark_source_quiet(), _orb_symbols() (+9 more)

### Community 11 - "test_circuit_breaker.py"
Cohesion: 0.07
Nodes (16): BotRuntime, get_daily_state(), get_runtime(), _last_opened_buy_at(), record_cycle_failure(), record_cycle_success(), record_realized_pnl(), register_open() (+8 more)

### Community 12 - "gray"
Cohesion: 0.05
Nodes (53): $type, $value, $type, $value, $type, $value, $type, $value (+45 more)

### Community 13 - "Settings"
Cohesion: 0.06
Nodes (9): Settings, _as_origin(), _cors_kwargs(), ConfigTests, _settings_without_env(), _apply_origins(), CorsHeaderTests, CorsSettingsTests (+1 more)

### Community 14 - "design_system.py"
Cohesion: 0.06
Nodes (19): ansi_ljust(), _button_outline_text_color(), _detect_page_type(), format_ascii_box(), add_wrapped(), wrap_text(), format_markdown(), format_master_md() (+11 more)

### Community 15 - "strategy_lab_service.py"
Cohesion: 0.11
Nodes (25): StrategyConfig, backtest_candles(), _close_position(), _close_position(), final_parameters_section(), grid_search_candles(), KlineBacktestConfig, KlineBacktestResult (+17 more)

### Community 16 - "test_orb_engine.py"
Cohesion: 0.12
Nodes (14): evaluate_orb(), _build(), DeterminismTests, _now_ny(), _ny(), NyDatetimeTests, NyDayStartTests, OrbBreakoutTests (+6 more)

### Community 17 - "report_service.py"
Cohesion: 0.09
Nodes (13): _breaker_text(), build_daily_report(), build_daily_report_html(), _collect_report(), _collect_summary(), ReportSummary, _state_text(), _summary_text() (+5 more)

### Community 18 - "bot.js"
Cohesion: 0.11
Nodes (29): getAiStats(), getBotMetrics(), getBotStatus(), getDecisions(), startBot(), stopBot(), getSources(), deriveOperationalState() (+21 more)

### Community 19 - "validate_data.py"
Cohesion: 0.11
Nodes (31): _catalog_date(), _check_app_interface_contract(), _check_catalog_contract(), _check_catalog_summary(), _check_color_contract(), _check_core_data_contract(), _check_file(), _check_font_catalog() (+23 more)

### Community 20 - "simulation.py"
Cohesion: 0.13
Nodes (31): account_arbitrages(), account_balance(), account_positions(), account_summary(), account_trades(), accounts(), bot_cycles(), bot_status() (+23 more)

### Community 21 - "SimulationAccountCreate"
Cohesion: 0.09
Nodes (11): SimulationAccountCreate, SimulationExecutor, create_simulation_account(), candles_15m(), KillSwitchTests, RiskEngineBase, candles_15m(), _ny_utc() (+3 more)

### Community 22 - "BinanceSpotClient"
Cohesion: 0.11
Nodes (4): BinanceAPIError, BinanceSpotClient, main(), BinanceSpotClientTest

### Community 23 - "BinanceExecutor"
Cohesion: 0.10
Nodes (7): BinanceExecutor, _points_to_production(), _to_decimal(), ExchangeBalance, ExchangeExecutor, ExchangeOrderResult, SymbolMetadata

### Community 24 - "._evaluate"
Cohesion: 0.10
Nodes (8): RiskAssessment, CorrelationTests, DelegationTests, ExposureTests, _falling_candles(), _flat_candles(), PositionLimitTests, _varied_candles()

### Community 25 - "OrbConfig"
Cohesion: 0.11
Nodes (11): _as_utc_naive(), in_orb_window(), ny_datetime(), ny_day_start_utc(), _ny_window(), OrbConfig, session_bounds(), _to_ny() (+3 more)

### Community 26 - "test_portfolio_math.py"
Cohesion: 0.12
Nodes (12): correlate_closes(), floor_to_step(), pct_returns(), pearson(), _require_decimal_list(), _constant(), CorrelateClosesTests, _falling() (+4 more)

### Community 27 - "Simulation.jsx"
Cohesion: 0.12
Nodes (21): createOrder(), App(), AccountSummary(), ICONS, MetricTile(), ICON_PATHS, NavRail(), scrollToWorkspace() (+13 more)

### Community 28 - "shutil"
Cohesion: 0.10
Nodes (16): _run(), test_creates_default_output_directory_when_missing(), test_dark_base_color_does_not_collapse_shades_to_black(), test_force_allows_sync_with_existing_css_token_source(), test_ignores_commented_root_custom_properties(), test_ignores_custom_properties_outside_root(), test_ignores_external_css_imports(), test_refuses_css_custom_property_source_without_force() (+8 more)

### Community 29 - "test_keepalive_service.py"
Cohesion: 0.08
Nodes (10): keepalive_loop(), run_ping(), should_keepalive(), _FakeClient, KeepaliveLoopTests, fake_get(), LifespanTests, fake_loop() (+2 more)

### Community 30 - "OKXDemoClient"
Cohesion: 0.12
Nodes (7): _compact_json(), _decimal_or_none(), _decimal_string(), _normalize_okx_status(), OKXAPIError, OKXDemoClient, main()

### Community 31 - "market_context_service.py"
Cohesion: 0.12
Nodes (21): clear_cache(), ContextSource, _disabled(), _Entry, FearGreedData, _fetch_cached(), _fetch_fear_greed(), _fetch_news() (+13 more)

### Community 32 - "bot_engine.py"
Cohesion: 0.13
Nodes (13): _calculate_revalidation_slippage(), evaluate_market(), execute_market(), _filter_fresh_executions(), _parse_fetched_at(), _prepare_market_evaluation(), get_available_balance(), validate_arbitrage_inventory() (+5 more)

### Community 33 - "test_core.py"
Cohesion: 0.06
Nodes (4): TestBm25CoreBehavior, TestDiagnosticsContracts, TestSearchDomains, TestTokenizer

### Community 34 - "replay_service.py"
Cohesion: 0.17
Nodes (17): decision_replay(), decision_why(), _resolve_decision(), _ai_block(), _decimal_text(), _decision_block(), _decision_correlation(), _event_block() (+9 more)

### Community 35 - "Candle"
Cohesion: 0.09
Nodes (11): Candle, _candles(), _candles(), _candles(), _buy_candles(), _FakeMarket, FakeMarketData, FakeMarketData (+3 more)

### Community 36 - "test_market_context.py"
Cohesion: 0.14
Nodes (10): ContextSnapshotTests, ContextTestBase, FakeClock, FakeDepthTickerMarket, FearGreedTests, NewsFeedTests, OrderBookTests, _raise() (+2 more)

### Community 37 - "BinanceMarketDataClient"
Cohesion: 0.13
Nodes (3): BinanceMarketDataClient, BinanceMarketDataClientTest, DepthAndTickerTests

### Community 38 - "package.json"
Cohesion: 0.08
Nodes (26): dependencies, axios, react, react-dom, name, private, scripts, build (+18 more)

### Community 39 - "react"
Cohesion: 0.12
Nodes (18): getDecisionReplay(), getDecisionWhy(), DecisionInspector(), ReplayView(), DECISIONES, REPLAY, WHY, REPLAY_FULL (+10 more)

### Community 40 - "html-token-validator.py"
Cohesion: 0.12
Nodes (12): get_context(), is_allowed_exception(), is_allowed_rgba(), is_inside_block(), load_css_variables(), main(), print_result(), print_summary() (+4 more)

### Community 41 - "send_email"
Cohesion: 0.12
Nodes (5): EmailSendError, send_email(), _send(), SendEmailTests, CliSendTests

### Community 42 - "backtest_orb"
Cohesion: 0.19
Nodes (8): backtest_orb(), grid_search_orb(), OrbBacktestConfig, _breakout(), _orb_candle(), _orb_series(), OrbKlineBacktestTest, _range_candles()

### Community 43 - "ai_advisor_service.py"
Cohesion: 0.21
Nodes (19): AnalysisOutcome, analyze(), _breaker_open(), _budget_exceeded(), _build_context(), _build_prompt(), _cached_evaluation(), _consult() (+11 more)

### Community 44 - "test_data_contracts.py"
Cohesion: 0.10
Nodes (8): apply_decision_rules(), _object_without_duplicates(), parse_decision_rules(), _validate_action(), split_values(), style_identities(), TestLandingAndStackContract, TestStyleIdentityContract

### Community 45 - "test_strategy_lab.py"
Cohesion: 0.19
Nodes (13): backtest(), BacktestResult, evaluate_snapshot(), _find_execution_at_exchange(), _future_snapshot_after_latency(), grid_search(), _locked_future_profit(), normalize_snapshot_quotes() (+5 more)

### Community 46 - "test_workflows.py"
Cohesion: 0.10
Nodes (5): _assert_secure(), DailyReportWorkflowTests, PagesWorkflowTests, _read(), RenderBlueprintTests

### Community 47 - "logo/generate.py"
Cohesion: 0.14
Nodes (15): _atlas_prediction_data(), _download_atlas_image(), _download_image(), _download_muapi_image(), _generate_with_atlas(), _generate_with_muapi(), _json_request(), load_env() (+7 more)

### Community 48 - "DesignSystemGenerator"
Cohesion: 0.12
Nodes (3): DesignSystemGenerator, TestReasoningMatch, TestEndToEndCoherence

### Community 49 - "test_core_data_quality.py"
Cohesion: 0.14
Nodes (11): read_rows(), TestAccessibilityGuidance, TestChartsTypographyAndIcons, TestCurrentReactGuidance, TestSemanticColors, _check_chart_contract(), _check_icon_contract(), _check_typography_contract() (+3 more)

### Community 50 - "AiEvaluation"
Cohesion: 0.15
Nodes (12): ai_analyze(), ai_recommendations(), ai_stats_endpoint(), AnalyzeRequest, _clamp_limit(), _resolve_symbol(), _serialize_evaluation(), _serialize_list_item() (+4 more)

### Community 51 - "observability.js"
Cohesion: 0.14
Nodes (15): getEvents(), getPipeline(), EventStream(), payloadSummary(), NodeBadge(), PipelineCanvas(), STATE_LABELS, STATE_TONES (+7 more)

### Community 52 - "pathlib"
Cohesion: 0.13
Nodes (3): LearningIsolationTests, main(), TestStackFlagWithDesignSystem

### Community 53 - "FakeMarketData"
Cohesion: 0.21
Nodes (5): CorrelationIdTests, candles_15m(), FakeMarketData, OrbWindowAndScopeTests, range_candles()

### Community 54 - "csv"
Cohesion: 0.12
Nodes (7): BM25, detect_domain(), get_cip_brief(), _load_csv(), search(), search_all(), _search_csv()

### Community 55 - "client.js"
Cohesion: 0.16
Nodes (15): api, API_BASE_URL, clearToken(), getToken(), setToken(), sendExternalSignal(), importClient(), ExternalSignalForm() (+7 more)

### Community 56 - "DepthBook"
Cohesion: 0.14
Nodes (7): reset_state(), DepthBook, Ticker24, FakeKlineMarket, FakeKlineMarket, FakeKlineMarket, FakeContextMarket

### Community 57 - "._nodes"
Cohesion: 0.19
Nodes (4): PipelineApiBase, PipelineCatalogTests, PipelineServiceNodesTests, PipelineSourceNodesTests

### Community 58 - "candidate_service.py"
Cohesion: 0.14
Nodes (9): FactorContribution, normalize_weights(), CandidateEntry, CandidatesResult, clamp_limit(), ExcludedEntry, get_candidates(), _mark_klines() (+1 more)

### Community 59 - "bot_runner_service.py"
Cohesion: 0.18
Nodes (14): SimulationBotCycle, BotRuntimeState, build_risk_config(), _build_symbol_summary(), execute_bot_cycle(), get_bot_cycles(), get_bot_status(), get_configured_symbols() (+6 more)

### Community 60 - "re"
Cohesion: 0.16
Nodes (9): apply_color(), apply_viewbox_size(), extract_svgs(), generate_batch(), generate_icon(), generate_sizes(), load_env(), main() (+1 more)

### Community 61 - "generate-slide.py"
Cohesion: 0.13
Nodes (11): _e(), generate_chart_slide(), generate_cta_slide(), generate_deck(), generate_metrics_slide(), generate_problem_slide(), generate_solution_slide(), generate_testimonial_slide() (+3 more)

### Community 63 - "spacing"
Cohesion: 0.09
Nodes (22): $type, $value, $type, $value, $type, $value, $type, $value (+14 more)

### Community 65 - "SignalAction"
Cohesion: 0.20
Nodes (8): evaluate(), SignalAction, SignalResult, BuySellCasesTests, _candles(), DeterminismTests, HoldCasesTests, PurityTests

### Community 66 - "_select_palette_for_mode"
Cohesion: 0.14
Nodes (7): _contrast_ratio(), _derive_dark_palette(), _palette_is_dark(), _relative_luminance(), _select_palette_for_mode(), TestLuminance, TestPaletteSelection

### Community 67 - "read_rows"
Cohesion: 0.17
Nodes (3): _resolve_dial(), read_rows(), TestReasoningContract

### Community 68 - "_handle_signal"
Cohesion: 0.16
Nodes (8): get_signal_decisions(), _handle_signal(), _persist_rejection(), post_external_signal(), post_webhook_signal(), _serialize(), _trading_symbols(), ExternalSignalRequest

### Community 69 - ".from_json"
Cohesion: 0.15
Nodes (3): AdvisorResponse, SchemaViolation, SchemaTests

### Community 70 - "OrderRejectedError"
Cohesion: 0.13
Nodes (6): OrderRejectedError, BinanceExecutorRulesTests, _BinanceExecutorTestCase, ClientOrderIdTests, _limit_request(), _spot_order_response()

### Community 71 - "MarketDataUnavailable"
Cohesion: 0.15
Nodes (5): MarketDataUnavailable, BrokenKlineMarket, _candles(), FakeCandidateMarket, _BrokenMarket

### Community 72 - "risk_engine_service.py"
Cohesion: 0.22
Nodes (8): _committed(), _correlations(), _decimal_text(), evaluate_open(), _exposure_cap(), exposure_snapshot(), limits_snapshot(), _open_positions()

### Community 73 - "fetch-background.py"
Cohesion: 0.15
Nodes (9): generate_css_for_background(), get_background_image(), get_curated_images(), get_overlay_css(), get_pexels_search_url(), load_backgrounds_config(), load_brand_colors(), main() (+1 more)

### Community 74 - "slide_search_core.py"
Cohesion: 0.16
Nodes (9): calculate_pattern_break(), detect_domain(), get_background_config(), get_color_for_emotion(), get_layout_for_goal(), get_typography_for_slide(), _load_decision_csv(), search_with_context() (+1 more)

### Community 76 - "collect_klines.py"
Cohesion: 0.18
Nodes (9): build_parser(), _candle_line(), CollectionError, download_symbol(), fetch_chunk(), interval_to_ms(), klines_file(), load_last_open_time() (+1 more)

### Community 77 - "color"
Cohesion: 0.11
Nodes (19): $type, $value, background, foreground, muted-foreground, primary, primary-hover, secondary (+11 more)

### Community 78 - "EventsEndpointTests"
Cohesion: 0.14
Nodes (4): EventsEndpointTests, ObservabilityApiBase, ObservabilityEndpointTests, SourcesEndpointTests

### Community 79 - "test_risk_capitals.py"
Cohesion: 0.22
Nodes (5): CapitalMatrixBase, CorrelatedSecondOpenTests, _flat_candles(), _ny_utc(), range_candles()

### Community 80 - "actionSystem.test.js"
Cohesion: 0.18
Nodes (10): css, jsxFiles, contrast(), css, luminance(), toRgb(), loadCss(), loadCssFiles() (+2 more)

### Community 81 - "main"
Cohesion: 0.14
Nodes (3): main(), _strip_to_object(), TestGeneratedConfigIsValidJs

### Community 83 - "OrderRequest"
Cohesion: 0.25
Nodes (3): OrderRequest, OKXDemoClientTest, RecordingExecutor

### Community 84 - "cip/generate.py"
Cohesion: 0.19
Nodes (7): build_cip_prompt(), check_logo_required(), generate_cip_set(), generate_with_nano_banana(), load_env(), load_logo_image(), main()

### Community 85 - "httpx"
Cohesion: 0.30
Nodes (13): _build_quote(), _coinbase_product_id(), _decimal(), fetch_binance_quote(), fetch_bybit_quote(), fetch_coinbase_quote(), fetch_exchange_quotes(), fetch_kraken_quote() (+5 more)

### Community 86 - "FakeMarketData"
Cohesion: 0.20
Nodes (3): EventTests, FakeMarketData, range_candles()

### Community 87 - "fontSize"
Cohesion: 0.12
Nodes (16): $type, $value, $type, $value, $type, $value, $type, $value (+8 more)

### Community 90 - "ReplayApiBase"
Cohesion: 0.27
Nodes (3): ReplayApiBase, ReplayPayloadTests, ReplayUnavailableTests

### Community 91 - "extract-colors.cjs"
Cohesion: 0.20
Nodes (11): calculateCompliance(), colorDistance(), displayPalette(), extractHexColors(), findNearestBrandColor(), fs, generateImageMagickCommand(), hexToRgb() (+3 more)

### Community 93 - "score_candidate"
Cohesion: 0.27
Nodes (4): score_candidate(), FeatureVector, ScoringTests, _vector()

### Community 94 - "_capture"
Cohesion: 0.20
Nodes (3): _capture(), _lines(), StructuredLogTests

### Community 95 - "devDependencies"
Cohesion: 0.14
Nodes (14): devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom, @testing-library/jest-dom (+6 more)

### Community 96 - "Simulation.test.jsx"
Cohesion: 0.38
Nodes (10): createAccount(), getAccounts(), getBalance(), getMarketPrices(), getPositions(), getSummary(), getTrades(), SUMMARY (+2 more)

### Community 97 - "sync-brand-to-tokens.cjs"
Cohesion: 0.20
Nodes (12): adjustBrightness(), CSS_TOKEN_SOURCES, { execFileSync }, extractColorsFromMarkdown(), findExistingTokenSources(), fs, GENERATE_TOKENS_SCRIPT, generateColorScale() (+4 more)

### Community 98 - "validate-asset.cjs"
Cohesion: 0.25
Nodes (13): checkManifest(), formatBytes(), formatOutput(), fs, main(), parseFilename(), path, RULES (+5 more)

### Community 99 - "radius"
Cohesion: 0.19
Nodes (14): $type, $value, $type, $value, $type, $value, primitive, radius (+6 more)

### Community 101 - "read_candidates"
Cohesion: 0.18
Nodes (6): read_candidates(), read_context(), resolve_symbols(), _serialize_candidates(), _serialize_context(), universe()

### Community 102 - "compute_features"
Cohesion: 0.26
Nodes (6): compute_features(), _pct_change(), _stdev(), _ema(), _metric(), _rsi()

### Community 103 - "test_feature_engine.py"
Cohesion: 0.27
Nodes (4): FeaturePeriods, _candle(), FeatureTests, _rising()

### Community 104 - "CandidatesApiBase"
Cohesion: 0.15
Nodes (4): CandidatesApiBase, CandidatesEndpointTests, ContextEndpointTests, EventTests

### Community 105 - "logo/core.py"
Cohesion: 0.21
Nodes (5): detect_domain(), _load_csv(), search(), search_all(), _search_csv()

### Community 106 - "vitest"
Cohesion: 0.28
Nodes (7): buildGeometry(), EquityChart(), TRADES, buildEquitySeries(), isPresent(), @testing-library/react, vitest

### Community 107 - "design-tokens-starter.json"
Cohesion: 0.15
Nodes (12): component, $type, $value, dark, semantic, $schema, $type, $value (+4 more)

### Community 109 - "test_text_layout_resilience.py"
Cohesion: 0.18
Nodes (3): read_rows(), TestTextLayoutDataContracts, TestTextLayoutRetrieval

### Community 110 - "argparse"
Cohesion: 0.24
Nodes (4): collect_snapshot(), main(), build_parser(), CollectMarketSnapshotsTest

### Community 112 - "embed-tokens.cjs"
Cohesion: 0.17
Nodes (8): args, fs, minimal, MINIMAL_TOKENS, path, projectRoot, tokensPath, wrapStyle

### Community 113 - "validate-tokens.cjs"
Cohesion: 0.24
Nodes (11): extensions, formatReport(), fs, getFiles(), main(), parseArgs(), path, patterns (+3 more)

### Community 114 - "card"
Cohesion: 0.20
Nodes (12): $type, $value, bg, bg, padding, shadow, card, bg (+4 more)

### Community 115 - "_style_is_dark_primary"
Cohesion: 0.21
Nodes (4): _query_wants_dark(), _resolve_color_mode(), _style_is_dark_primary(), TestModeResolution

### Community 116 - "render-html.py"
Cohesion: 0.25
Nodes (4): generate_html(), get_deliverable_info(), get_image_base64(), main()

### Community 117 - "_session_factory"
Cohesion: 0.18
Nodes (3): AggregatesTests, _session_factory(), SourceHealthTests

### Community 119 - "inject-brand-context.cjs"
Cohesion: 0.31
Nodes (10): extractColorsFromTable(), extractCoreAttributes(), extractHexColors(), extractImageStyle(), extractTypography(), extractVoice(), fs, generatePromptAddition() (+2 more)

### Community 120 - "search-slides.py"
Cohesion: 0.27
Nodes (5): format_context(), format_result(), main(), search(), search_all()

### Community 121 - "generate-tokens.cjs"
Cohesion: 0.36
Nodes (9): flattenTokens(), fs, generateCSS(), generateTailwind(), main(), parseArgs(), path, resolveReference() (+1 more)

### Community 122 - "button"
Cohesion: 0.20
Nodes (10): fg, font-size, hover-bg, button, $type, $value, $type, $value (+2 more)

### Community 123 - "duration"
Cohesion: 0.20
Nodes (10): fast, normal, slow, $type, $value, $type, $value, duration (+2 more)

### Community 128 - "arbitrage_service.py"
Cohesion: 0.44
Nodes (6): execute_arbitrage(), _find_execution(), get_arbitrages(), get_balance_record(), money(), quantity_value()

### Community 131 - "ExecutionModeTests"
Cohesion: 0.31
Nodes (4): ExecutionModeTests, router(), _request(), _spot_order_response()

### Community 134 - "test_validate_tokens.py"
Cohesion: 0.28
Nodes (3): _run(), test_flags_hardcoded_hex_sharing_line_with_token(), test_token_only_line_reports_no_violation()

### Community 135 - "cip/search.py"
Cohesion: 0.32
Nodes (3): format_brief(), format_results(), main()

### Community 137 - "_render_html"
Cohesion: 0.32
Nodes (6): _e(), _html_card(), _html_row(), _render_html(), ReportData, _state_color()

### Community 139 - "Session"
Cohesion: 0.57
Nodes (7): get_account(), get_balance(), get_market_prices(), get_positions(), get_summary(), get_trades(), reset_simulation_account()

### Community 141 - "ChunkDownloadAndResumeTests"
Cohesion: 0.32
Nodes (4): ChunkDownloadAndResumeTests, flaky_request(), resumed_request(), _rows()

### Community 145 - "generate_logo"
Cohesion: 0.29
Nodes (5): enhance_prompt(), generate_batch(), generate_logo(), _generate_with_gemini(), main()

### Community 146 - "input"
Cohesion: 0.29
Nodes (8): padding-x, input, $type, $value, focus-ring, padding-x, $type, $value

### Community 149 - "candidate_engine.py"
Cohesion: 0.43
Nodes (3): CandidateScore, _clamp(), _normalize()

### Community 150 - "run_daily_pass"
Cohesion: 0.38
Nodes (3): _guard_elapsed(), run_daily_pass(), _trading_symbols()

### Community 155 - "test_skill_script_paths.py"
Cohesion: 0.38
Nodes (3): resolve(), shipped_invocations(), SkillScriptPathsTest

### Community 156 - "select_best_execution"
Cohesion: 0.67
Nodes (4): aggregate_market_prices(), calculate_buy_execution(), calculate_sell_execution(), select_best_execution()

### Community 158 - "_num"
Cohesion: 0.40
Nodes (3): _balance_and_pnl_lines(), _daily_line(), _num()

### Community 165 - "find_best_opportunity"
Cohesion: 0.80
Nodes (4): calculate_opportunity(), _decimal(), _extract_base_asset(), find_best_opportunity()

### Community 169 - "$type"
Cohesion: 0.60
Nodes (5): $type, $value, border, border, border

### Community 170 - "radius"
Cohesion: 0.60
Nodes (5): radius, radius, radius, $type, $value

### Community 171 - "lg"
Cohesion: 0.60
Nodes (5): lg, $type, $value, lg, lg

### Community 172 - "sm"
Cohesion: 0.60
Nodes (5): sm, sm, sm, $type, $value

### Community 179 - "padding-y"
Cohesion: 0.67
Nodes (4): padding-y, padding-y, $type, $value

### Community 180 - "xl"
Cohesion: 0.67
Nodes (4): xl, xl, $type, $value

### Community 181 - "none"
Cohesion: 0.67
Nodes (4): $type, $value, none, none

### Community 187 - "16"
Cohesion: 0.67
Nodes (3): $type, $value, 16

### Community 188 - "1"
Cohesion: 0.67
Nodes (3): $type, $value, 1

### Community 189 - "3"
Cohesion: 0.67
Nodes (3): $type, $value, 3

### Community 190 - "8"
Cohesion: 0.67
Nodes (3): $type, $value, 8

### Community 191 - "destructive"
Cohesion: 0.67
Nodes (3): destructive, $type, $value

### Community 192 - "destructive-foreground"
Cohesion: 0.67
Nodes (3): destructive-foreground, $type, $value

### Community 193 - "muted"
Cohesion: 0.67
Nodes (3): muted, $type, $value

### Community 194 - "primary-foreground"
Cohesion: 0.67
Nodes (3): primary-foreground, $type, $value

### Community 195 - "ring"
Cohesion: 0.67
Nodes (3): ring, $type, $value

### Community 196 - "secondary-foreground"
Cohesion: 0.67
Nodes (3): secondary-foreground, $type, $value

## Knowledge Gaps
- **3 isolated node(s):** `jsdom`, `@types/react`, `@types/react-dom`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1218 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **54 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Candle` connect `Candle` to `Base`, `DecisionStatus`, `bot_loop.py`, `test_circuit_breaker.py`, `strategy_lab_service.py`, `test_orb_engine.py`, `SimulationAccountCreate`, `._evaluate`, `OrbConfig`, `BinanceMarketDataClient`, `backtest_orb`, `test_strategy_lab.py`, `FakeMarketData`, `DepthBook`, `SignalAction`, `MarketDataUnavailable`, `test_risk_capitals.py`, `FakeMarketData`, `compute_features`, `test_feature_engine.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 45 inferred relationships involving `SignalDecision` (e.g. with `_resolve_decision()` and `_serialize()`) actually correct?**
  _`SignalDecision` has 45 INFERRED edges - model-reasoned connections that need verification._
- **What connects `jsdom`, `@types/react`, `@types/react-dom` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Base` be split into smaller, more focused modules?**
  _Cohesion score 0.06904761904761905 - nodes in this community are weakly interconnected._
- **Why does `TailwindConfigGenerator` connect `TailwindConfigGenerator` to `TestTailwindConfigGenerator`, `main`, `.validate_config`, `.add_plugins`, `.generate_config_string`, `._base_config`, `.test_full_configuration_typescript`, `.write_config`, `.add_colors`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `Candle` (e.g. with `compute_features()` and `evaluate_orb()`) actually correct?**
  _`Candle` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Should `json` be split into smaller, more focused modules?**
  _Cohesion score 0.0636030636030636 - nodes in this community are weakly interconnected._