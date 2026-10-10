# Screener (Python + MetaTrader 5)

Scans a list of tickers with the trend + pullback rules and prints one row per symbol.

```text
MT5 terminal ──► MetaTrader5 package ──► rules.py ──► table (console / CSV)
                  D1, W1, H4 bars        layer 1, arrows, layer 2
```

## Setup (Windows, MT5 installed and logged in to your broker)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python screener.py --source mt5 --symbols PETR4 VALE3 BBAS3
```

Put one ticker per line in a text file and use `--symbols-file tickers.txt` for longer lists. Add `--out results.csv` to save the table.

## Output columns

| Column | Meaning |
|---|---|
| `trend_L1` | UP / DOWN / `-`: close above (below) EMA9, SMA20 and SMA200 on the daily chart |
| `trend_L2` | UP / DOWN / `-`: layer 1 and the 4h, daily and weekly trends all agree |
| `pullback_today` | UP / DOWN / `-`: an arrow on the last bar |
| `bars_since_pullback`, `last_pullback` | how long ago the last arrow was |
| `dist_sma20_pct` | distance of the close from the SMA20, in percent |

## Options

- `--mt5-path PATH`: full path to `terminal64.exe`, needed when several MT5 terminals are installed, e.g. `--mt5-path "C:\Program Files\MetaTrader 5\terminal64.exe"`. The terminal must be open and logged in.
- `--weekly-mode live` (default): the last daily bar uses the developing weekly bar, like a live chart. `completed` uses only finished weeks, which is what to use for backtests.
- `--history TICKER`: print the whole per-day table for one symbol, for checking against a chart.
- `--source csv --folder DIR`: read exported MT5 CSV files instead of a live terminal (useful on non-Windows machines and for checking).
- `--allow-short-history`: ignore a missing SMA200. For validation on short samples only, never for real screening.

## Notes and limits

- Run it after the close, so the daily bar is final.
- The weekly SMA200 needs about 200 weekly bars. The script asks MT5 for 400. If your broker has less history, layer 2 will stay off.
- MT5 H4 bars on B3 come as three per day. The last two are merged to mimic TradingView's two 4h bars, so a few edge bars can differ from TradingView.
- Data from MT5 and TradingView can differ slightly (adjustments), so a close within a cent or two of an average can flip.
- Research tool, not financial advice.

## Tests

```bash
pip install pytest
python -m pytest tests
```
