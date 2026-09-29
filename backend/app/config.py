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

    simulation_bot_symbols: str = (
        "BTCUSDT,ETHUSDT,SOLUSDT"
    )

    simulation_bot_capital_usd: Decimal = Decimal("5")

    simulation_bot_max_trade_usd: Decimal = Decimal("5")
    simulation_bot_min_profit_usd: Decimal = Decimal("0.05")
    simulation_bot_min_profit_percent: Decimal = Decimal("0.10")
    simulation_bot_min_liquidity_usd: Decimal = Decimal("10")
    simulation_bot_max_position_usd: Decimal = Decimal("20")

    simulation_bot_cooldown_seconds: int = 300
    simulation_bot_max_trades_per_day: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()