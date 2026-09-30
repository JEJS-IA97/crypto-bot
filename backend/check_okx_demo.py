from app.config import settings
from app.services.okx_demo_client import OKXAPIError, OKXDemoClient


def main() -> None:
    client = OKXDemoClient()
    if not client.is_configured:
        raise SystemExit(
            "Set OKX_DEMO_API_KEY, OKX_DEMO_API_SECRET and "
            "OKX_DEMO_API_PASSPHRASE in backend/.env before running this check."
        )

    print("Checking OKX Demo Trading Spot connectivity...")
    offset = client.sync_time()
    print(f"Clock offset: {offset} ms")

    balances = client.get_balances()
    print(f"Balances returned: {len(balances)}")
    for balance in balances:
        print(
            f"  {balance.asset}: available={balance.available} "
            f"locked={balance.locked}"
        )

    metadata = client.get_symbol_metadata("BTCUSDT")
    print(f"BTCUSDT state: {metadata.status}")
    print(f"BTCUSDT base/quote: {metadata.base_asset}/{metadata.quote_asset}")
    print(f"BTCUSDT quantity step: {metadata.quantity_step}")
    print(f"BTCUSDT price tick: {metadata.price_tick}")
    print("OKX Demo Trading Spot connection OK.")


if __name__ == "__main__":
    try:
        main()
    except OKXAPIError as exc:
        raise SystemExit(f"OKX API error: {exc}") from exc
