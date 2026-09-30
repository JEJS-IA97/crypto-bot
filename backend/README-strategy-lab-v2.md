# Strategy Lab — realism fix

This stage fixes two important backtesting problems before we collect a large dataset.

1. Exchange legs are locked at signal time. After simulated latency, the backtest re-prices the same buy exchange and the same sell exchange. It does not re-select the best exchanges using future data, avoiding look-ahead bias.

2. Negative outcomes after latency now affect simulated equity and max drawdown instead of being discarded. `survived_samples` counts only profitable outcomes, while `total_proxy_profit_usd` includes losing trades.

Run:

```powershell
python -m unittest tests/test_strategy_lab.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall app tests
```

Do not start multi-hour collection until these tests pass.
