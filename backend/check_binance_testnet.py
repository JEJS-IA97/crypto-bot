from app.config import settings
from app.services.binance_spot_client import BinanceAPIError, BinanceSpotClient


def main() -> None:
    client = BinanceSpotClient(settings.binance_api_key, settings.binance_api_secret, settings.binance_testnet_base_url, settings.binance_recv_window_ms)
    if not client.is_configured:
        raise SystemExit("Set BINANCE_API_KEY and BINANCE_API_SECRET in backend/.env before running this check.")
    print("Checking Binance Spot Testnet connectivity...")
    offset = client.sync_time()
    print(f"Clock offset: {offset} ms")
    print(f"Ping: {client.ping()}")
    account = client.get_account(omit_zero_balances=True)
    print(f"Account type: {account.get('accountType')}")
    print(f"Permissions: {account.get('permissions', [])}")
    for balance in account.get("balances", []):
        print(f"  {balance['asset']}: free={balance['free']} locked={balance['locked']}")
    info = client.get_symbol_info("BTCUSDT")
    print(f"BTCUSDT status: {info.get('status')}")
    print(f"BTCUSDT order types: {info.get('orderTypes', [])}")
    print("Binance Spot Testnet connection OK.")


if __name__ == "__main__":
    try:
        main()
    except BinanceAPIError as exc:
        raise SystemExit(f"Binance API error: {exc}") from exc
