# Strategy Lab

This stage adds a local strategy-training/backtesting layer without requiring exchange credentials or real funds.

The lab consumes public quote snapshots collected from the existing exchange market service, evaluates cross-exchange opportunities with the project's fee model, simulates an assumed execution latency, applies a configurable slippage penalty, and compares strategy configurations on chronological train/validation/test segments.

It is intentionally not wired to autonomous order execution. The output is a research signal, not proof of profitability.

## Collect market data

From `backend`:

```powershell
python collect_market_snapshots.py --symbol BTCUSDT --symbol ETHUSDT --interval 5 --duration 3600 --output data/market_snapshots.jsonl
```

The collector uses public market data only. No API key is needed.

## Run the strategy optimizer

```powershell
python train_strategy.py data/market_snapshots.jsonl
```

## Tests

```powershell
python -m unittest tests/test_strategy_lab.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall app tests
```

The lab currently optimizes threshold, assumed latency and slippage configurations. It deliberately does not call any exchange order endpoint.
