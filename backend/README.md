# Crypto bot - quote age and slippage controls

Changes in this bundle:

- Every successful exchange quote now includes `fetched_at` in UTC ISO-8601.
- Execution prices carry that timestamp forward.
- Market evaluation rejects buy/sell executions whose quote is older than `SIMULATION_BOT_MAX_QUOTE_AGE_SECONDS`.
- Missing or invalid quote timestamps fail closed.
- During execution revalidation, the bot calculates adverse movement separately for the buy and sell legs.
- Execution is blocked when adverse movement exceeds `SIMULATION_BOT_MAX_SLIPPAGE_PERCENT`.
- Revalidation failures now distinguish `opportunity_disappeared` and `slippage_exceeded`.
- No database schema change is required.

Recommended `.env` values for the current simulation:

SIMULATION_BOT_MAX_QUOTE_AGE_SECONDS=5
SIMULATION_BOT_MAX_SLIPPAGE_PERCENT=0.20

Run from `backend`:

python -m unittest tests/test_quote_execution_controls.py
python -m compileall app tests

Then keep the existing bot running and inspect:

GET /simulation/bot/status

For a stale quote, the cycle reason becomes:
No fresh executable market quote is available.

For revalidation slippage:
Market moved beyond configured slippage tolerance during execution revalidation.
