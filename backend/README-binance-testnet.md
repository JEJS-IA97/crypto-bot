# Binance Spot Testnet integration

This bundle adds the first authenticated Binance Spot REST adapter. It is deliberately limited to Spot REST endpoints and does not implement futures, margin, transfers, or withdrawals.

The official Spot Test Network uses `https://testnet.binance.vision/api` for REST. Binance documents `POST /api/v3/order/test` as a signed endpoint that validates an order without sending it to the matching engine. Account, order status, order placement and cancellation are also available through signed Spot endpoints.

Setup:

1. Generate a Binance Spot Testnet API key.
2. Put the key and secret only in `backend/.env`.
3. Never commit `.env` or paste the secret into chat.
4. From `backend`, run `python check_binance_testnet.py`.
5. Run `python -m unittest tests/test_binance_spot_client.py`.
6. Run `python -m unittest discover -s tests -p "test_*.py"` and `python -m compileall app tests`.

This bundle does not yet connect the autonomous strategy directly to live order placement. The next execution layer must handle order lifecycle, partial fills, timeouts, cancellation, and balance reconciliation before the strategy can place real orders.
