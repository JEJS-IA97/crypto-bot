from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CryptoBot API"
    app_version: str = "0.1.0"

    database_url: str = "sqlite:///./crypto_bot.db"

    simulation_initial_balance: float = 20.0
    simulation_fee_rate: float = 0.001

    simulation_bot_enabled: bool = False
    simulation_bot_interval_seconds: int = 60

    simulation_bot_account_id: int = 1

    simulation_bot_symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT"

    simulation_bot_capital_usd: Decimal = Decimal("5")

    simulation_bot_max_trade_usd: Decimal = Decimal("5")
    simulation_bot_min_profit_usd: Decimal = Decimal("0.05")
    simulation_bot_min_profit_percent: Decimal = Decimal("0.10")
    simulation_bot_min_liquidity_usd: Decimal = Decimal("10")
    simulation_bot_max_position_usd: Decimal = Decimal("20")

    simulation_bot_max_quote_age_seconds: int = 5
    simulation_bot_max_slippage_percent: Decimal = Decimal("0.20")

    simulation_bot_cooldown_seconds: int = 300
    simulation_bot_max_trades_per_day: int = 3

    # Phase 1: Binance Spot single-exchange trading (spec 001, RF-1/RF-2/RF-8/RF-13).
    allow_live_trading: bool = False
    configured_capital_usd: Decimal = Decimal("20")
    api_token: str = ""

    trading_symbols: str = (
        "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,LINKUSDT"
    )
    # Pares con señal técnica ORB (spec 001, D-12); el resto solo externas.
    orb_symbols: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT"
    trading_interval_seconds: int = 60

    stop_loss_pct: Decimal = Decimal("2.0")
    # D-11: RR 1:1 — take-profit igual al stop-loss (2% por defecto).
    take_profit_pct: Decimal = Decimal("2.0")
    max_signal_price_distance_pct: Decimal = Decimal("1.0")
    signal_ttl_seconds: int = 300

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet_base_url: str = "https://testnet.binance.vision"
    binance_recv_window_ms: int = 5000
    # Host de datos públicos (klines/exchangeInfo). En la nube puede ser
    # data-api.binance.vision si api.binance.com bloquea la IP del proveedor.
    binance_market_data_base_url: str = "https://api.binance.com"

    okx_demo_api_key: str = ""
    okx_demo_api_secret: str = ""
    okx_demo_api_passphrase: str = ""
    okx_demo_base_url: str = "https://openapi.okx.com"
    okx_demo_timeout_seconds: float = 10.0

    # Informe diario por correo (spec 002, RF-7). Vacío = fail-closed (RF-4).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    report_to: str = ""

    # Keepalive antispin-down de Render free (spec 002, RF-1). Vacío = off.
    keepalive_url: str = ""

    # Orígenes CORS permitidos, CSV (spec 002, RF-8). En despliegue incluir
    # la URL de GitHub Pages; en local, el dev server de Vite.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173"
    )

    # Observabilidad (spec 005, RF-1/RF-8): retencion de eventos en dias,
    # nivel de log y version de estrategia que viaja en cada evento.
    event_retention_days: int = 30
    log_level: str = "INFO"
    strategy_version: str = "orb-001-v3"

    # Datos y contexto (spec 006, D-2): fuentes declaradas. URL vacia =
    # fuente DISABLED sin llamada HTTP; RSS en CSV (vacio = sin noticias).
    fear_greed_url: str = "https://api.alternative.me/fng/"
    news_rss_feeds: str = ""
    # TTL de la caché en memoria (segundos): depth 30s, F&G 6h, news 15min.
    depth_cache_seconds: int = 30
    fear_greed_cache_seconds: int = 21600
    news_cache_seconds: int = 900
    # Pesos del score de candidatos (RF-6): CSV "clave:peso". Vacio o
    # invalido → DEFAULT_WEIGHTS de candidate_engine.
    candidate_weights: str = "momentum:0.30,volume:0.25,trend:0.25,range:0.20"

    # Analista IA (spec 007, D-2): solo tier gratuito, presupuesto 0 USD.
    # Clave vacia = DISABLED; NUNCA se habilita pago (punto 4 de la
    # constitucion). El modelo se confirma con la doc oficial al crearla.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta"
    )
    gemini_timeout_seconds: int = 10
    gemini_max_retries: int = 2
    gemini_daily_query_limit: int = 4
    gemini_cache_seconds: int = 3600
    gemini_breaker_failures: int = 3
    gemini_breaker_seconds: int = 900
    # Pasada diaria opcional (RF-8); el loop de la 001 no se toca.
    gemini_auto_analysis: bool = False
    gemini_auto_analysis_limit: int = 3
    # Coste en USD: precios por millon de tokens; 0 = sin coste registrado.
    gemini_daily_budget_usd: Decimal = Decimal("0")
    gemini_price_mtok_input: Decimal = Decimal("0")
    gemini_price_mtok_output: Decimal = Decimal("0")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()