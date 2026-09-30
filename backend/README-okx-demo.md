# OKX Demo Trading Spot adapter

This stage adds the exchange-execution foundation without connecting the autonomous bot to live execution.

Added:

- `app/services/exchange_executor.py`: normalized exchange interface and order/balance/metadata types.
- `app/services/okx_demo_client.py`: authenticated OKX Demo Trading Spot REST client.
- `app/services/simulation_executor.py`: adapter around the existing simulation service.
- `check_okx_demo.py`: safe connectivity and account/metadata check.
- `tests/test_okx_demo_client.py`: signing, demo header, order payload and balance normalization tests.

The OKX client is explicitly limited to Spot `cash` trading and does not implement margin, futures, swaps, transfers, deposits or withdrawals.

No API secret belongs in Git. Put the three Demo Trading credentials only in `backend/.env`.

The bot engine is intentionally not wired to this executor yet. Before that, we still need persistent order lifecycle, exchange-specific inventory, market-rule validation, fill reconciliation and two-leg arbitrage recovery handling.
