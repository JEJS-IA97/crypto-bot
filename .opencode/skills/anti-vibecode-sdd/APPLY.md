# Apply collector fix

Copy these files preserving paths:

- `backend/collect_market_snapshots.py`
- `backend/tests/test_collect_market_snapshots.py`
- `backend/README-collector-fix.md`

Then from `backend`:

```powershell
python -m unittest tests/test_collect_market_snapshots.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall app tests
```

Then:

```powershell
python collect_market_snapshots.py --symbol BTCUSDT --symbol ETHUSDT --symbol SOLUSDT --interval 5 --duration 21600 --output data/market_snapshots.jsonl
```