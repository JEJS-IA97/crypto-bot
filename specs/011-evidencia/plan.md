# Plan — Spec 011 (Evidencia: walk-forward ORB)

Contratos y piezas previstos. La spec manda; si un contrato choca con la implementación, se cambia el plan, no la spec sin aprobación. Todo offline: sin BD, sin API, sin red, sin tocar 001–010.

## Piezas nuevas (2 ficheros + directorio de salidas)

### Servicio (`backend/app/services/walk_forward_service.py`)

Módulo puro (dataclasses + funciones), `Decimal` en todo, sin imports de runtime del bot. Reutiliza de `strategy_lab_service`: `load_klines_jsonl`, `split_candles`, `backtest_orb`, `grid_search_orb` (si encaja con la selección train/valid; si no, bucle propio de candidatos), `OrbBacktestConfig`, `KlineTrade`, `KlineBacktestResult`.

Contratos:

```python
@dataclass(frozen=True)
class WalkForwardConfig:
    symbols: tuple[str, ...]           # default: orb_symbols de config.py (4 pares)
    interval: str = "5m"
    train_days: int = 180
    test_days: int = 30
    step_days: int = 30
    validation_ratio: float = 0.15     # fracción final del train (const. #9)
    fee_rate: Decimal = Decimal("0.0010")     # 0.10 % por lado
    slippage_pct: Decimal = Decimal("0.05")   # 0.05 % por lado
    capital_usd: Decimal = Decimal("20")
    stop_loss_grid: tuple[Decimal, ...] = (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))
    take_profit_grid: tuple[Decimal, ...] = (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))
    data_dir: Path                     # data/klines por defecto

@dataclass(frozen=True)
class FoldMetrics:
    net_pnl_usd: Decimal
    return_pct: Decimal                # sobre capital_usd de la ventana
    max_drawdown_usd: Decimal
    max_drawdown_pct: Decimal
    sharpe: Decimal                    # D-5, 0 si <2 días o desv 0
    profit_factor: Decimal | None      # None => "n/a" en el reporte
    expectancy_usd: Decimal
    trades: int
    winning_trades: int
    fees_usd: Decimal

@dataclass(frozen=True)
class FoldResult:
    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    best_stop_loss_pct: Decimal
    best_take_profit_pct: Decimal
    train_trades: int                  # del fold ganador sobre train completo
    validation_pnl_usd: Decimal
    metrics: FoldMetrics               # sobre el test

@dataclass(frozen=True)
class WalkForwardResult:
    config: WalkForwardConfig
    folds: tuple[FoldResult, ...]
    aggregate: FoldMetrics             # suma aritmética de PnL de test + métricas agregadas
    buy_hold_usd: dict[str, Decimal]   # por símbolo, informativo
    verdict: str                       # "PASA" | "NO PASA"
```

Funciones:

- `build_folds(candles_by_symbol, config) -> list[tuple[range de fechas]]` — construcción exacta D-3; error si no cabe un fold (D-8).
- `validate_candles(candles) -> None` — D-8 (timestamps estrictos, Decimal, OHLC).
- `iter_grid(config) -> Iterable[OrbBacktestConfig]` — descarta candidatos con `capital * stop_loss_pct/100 > 1 USD` (const. #3).
- `select_params(train, validation, grid, config) -> tuple[Decimal, Decimal]` — mejor por PnL de validación; empate ⇒ menor SL, luego menor TP (conservador).
- `run_walk_forward(config) -> WalkForwardResult` — orquestador: carga+valida, folds, por fold (select sobre train[−15 %] como valid, backtest test), agregado, buy & hold, gate `PASA ⇔ aggregate.net_pnl_usd > 0`.
- `daily_sharpe(equity_by_day: list[Decimal]) -> Decimal` — D-5 (poblacional × √252, sin riesgo libre).
- `max_drawdown(equity_curve: list[Decimal]) -> tuple[Decimal, Decimal]`.
- `render_report(result) -> str` — Markdown español (RF-5), incluye buy & hold por símbolo, huecos entre tests marcados y veredicto.

### CLI (`backend/run_walk_forward.py`)

Espejo del patrón de `collect_klines.py` (argparse, `__main__`, sin dependencias nuevas):

```
python run_walk_forward.py [--symbols BTCUSDT,...] [--train-days 180]
    [--test-days 30] [--step-days 30] [--data-dir data/klines]
    [--fee-rate 0.0010] [--slippage-pct 0.05] [--output-dir reports]
```

- Carga `Settings` para `orb_symbols` por defecto; escribe `reports/walk-forward-<UTC timestamp>.md`.
- Exit 0 = corrida completada (sea PASA o NO PASA); exit 1 = error de entrada/dataset (RF-7). Imprime ruta del reporte y veredicto por consola.

### Salidas

- `backend/reports/` (creado on demand; relativo al cwd `backend/`, que es como se ejecutan los comandos del proyecto). `.gitignore` += `backend/reports/` si no está cubierto.

## Qué NO se toca

- `strategy_lab_service.py` (solo se importa), `app/models.py`, API, frontend, `bot_loop`, riesgo, BD. Sin dependencias nuevas.

## Fórmulas fijadas (D-5, RF-4)

- Equity por ventana: 20 USD al abrir cada test; curva = equity tras cada trade.
- Retorno neto % = `net_pnl / capital * 100`.
- Drawdown máx. sobre la curva de equity (USD y % del pico).
- Sharpe diario: serie de equity al cierre de **cada día calendario** del test (días sin trades ⇒ equity plana ⇒ retorno 0); `media/desv_poblacional × √252`; `<2` días o desv 0 ⇒ 0.
- Profit factor = `Σganancias / |Σpérdidas|`; `Σpérdidas = 0` ⇒ `None` ("n/a").
- Expectancy = `net_pnl / trades`; 0 trades ⇒ 0.
- Agregado: suma aritmética de PnL de test (D-7); métricas agregadas recalculadas sobre la concatenación de curvas diarias de todos los tests (sin continuidad de capital).
- Buy & hold por símbolo: `20 USD × (close_último / close_primero − 1)` sobre `[primer test start, último test end]`, informativo.

## Estrategia de tests (TDD, rojo→verde)

Fixtures: JSONL sintéticos en dir temporal, ventana pequeña (train 10 d / test 5 d / paso 5 d ⇒ ~40 d × 72 velas/día ≈ 2 880 velas/símbolo), generador en `tests/fixtures_klines.py` (velas 5m con sesión NY 9:00–10:00 poblada para que ORB opere).

| Test | RF | Qué prueba |
|------|----|-----------|
| `test_walk_forward.py` | RF-1, RF-2, RF-9 | validación de velas (corruptas ⇒ error); construcción de folds (fechas exactas D-3); **sin look-ahead**: pico gigante solo en test que cambiaría el ganador si se filtrara al train; determinismo (2 corridas ⇒ mismos números; sin float en la salida) |
| `test_wf_metrics.py` | RF-3, RF-4 | costes aplicados (comisión+slippage visibles en fees); las 5 métricas contra valores calculados a mano en micro-dataset; casos límite 5/6 (profit factor n/a, Sharpe 0) |
| `test_walk_forward_cli.py` | RF-5, RF-6, RF-7 | Markdown contiene secciones obligatorias y veredicto; PASA ⇔ agregado > 0 (fixtures positivas y negativas); exit 0 completada / exit 1 dataset ausente |
| `test_walk_forward_isolation.py` | RF-8 | sin red (no se importa httpx/requests en el grafo de la corrida), sin tocar DB ni `bot_loop` |

Al final de cada tarea: suite completa + `ruff check` + `compileall`; reporte RF cubiertos y **PÁRATE**.

## Orden de tareas (referencia para fase Tareas)

- T1 · Tests rojos: fixtures + `build_folds`/`validate_candles` (RF-1/2/9).
- T2 · Verde folds + grid + selección train/valid (RF-2, const. #3/#9).
- T3 · Métricas y agregado (RF-3/4) rojo→verde.
- T4 · Gate, reporte, CLI (RF-5/6/7) rojo→verde.
- T5 · Aislamiento (RF-8), `.gitignore`, suite completa, docs (READMEs + estado), validación RF por RF.
