# Apply this stage

Start from the current `master` commit that contains the OKX execution foundation. Do not remove or modify the existing OKX files.

Copy these files into the repository root, preserving paths:

- `backend/app/services/strategy_lab_service.py`
- `backend/collect_market_snapshots.py`
- `backend/train_strategy.py`
- `backend/tests/test_strategy_lab.py`
- `backend/README-strategy-lab.md`

Then from `backend` run:

```powershell
python -m unittest tests/test_strategy_lab.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall app tests
```

The collector uses only public market data. Do not add API keys to this stage.
