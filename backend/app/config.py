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
    trading_interval_seconds: int = 60

    stop_loss_pct: Decimal = Decimal("2.0")
    take_profit_pct: Decimal = Decimal("4.0")
    max_signal_price_distance_pct: Decimal = Decimal("1.0")
    signal_ttl_seconds: int = 300

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet_base_url: str = "https://testnet.binance.vision"
    binance_recv_window_ms: int = 5000

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()