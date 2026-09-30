# Collector fix

The snapshot collector now creates the parent directory of `--output` automatically.

Run from `backend`:

```powershell
python -m unittest tests/test_collect_market_snapshots.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall app tests
```

Then start collection:

```powershell
python collect_market_snapshots.py --symbol BTCUSDT --symbol ETHUSDT --symbol SOLUSDT --interval 5 --duration 21600 --output data/market_snapshots.jsonl
```

The collector uses public market data only. No API keys are required.
