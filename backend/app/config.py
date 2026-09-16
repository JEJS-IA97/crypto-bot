from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CryptoBot API"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./crypto_bot.db"
    simulation_initial_balance: float = 20.0
    simulation_fee_rate: float = 0.001

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()