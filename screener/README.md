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
python screener.py --symbols PETR4 VALE3 BBAS3
```

Put one ticker per line in a text file and use `--symbols-file tickers.txt` for longer lists. Add `--out results.csv` to save the table.

## Dashboard (static report)

```bash
python screener.py --source mt5 --mt5-path "C:\Program Files\MetaTrader 5\terminal64.exe" --symbols-file tickers.txt --db screener.db
python report.py --db screener.db --out report.html
```

`--db` stores each run in SQLite (`store.py`): the last 260 daily bars per symbol, plus one snapshot row per symbol and as-of date. `report.py` turns the latest snapshot into one self-contained HTML file with no server and no network. Open it in a browser.

- The table is grouped by what matters (arrow today, layer 2 aligned, layer 1 trend, no trend) and filterable.
- The **Changes** column compares with the symbol's previous stored snapshot (arrow fired, layer 1 or layer 2 entered or left), so run the screener once per day after the close.
- Click a symbol for the price chart with EMA9, SMA20, SMA200, layer 1 and 2 shading, arrows, a per-day state strip and a data table.
- Re-running on the same as-of date overwrites that day's snapshot (the live bar can still move).

## Data sources

`--source auto` (the default) tries MT5 first and falls back to Yahoo Finance (`yfinance`). It is **all or nothing**: if MT5 cannot start, or misses even one symbol, every symbol is re-fetched from Yahoo Finance and the MT5 results are discarded. A screen never mixes sources, because the two vendors' numbers differ slightly. Force one with `--source mt5`, `--source yfinance` or `--source csv`.

- The source is stored with each snapshot and shown in the report header. If the source changes between two runs, the Changes column says so, since a flip may then come from the data and not the market.
- Yahoo has no 4h bars, so they are built from 1h bars, two per day (10:00 to 13:59, and 14:00 to close). This approximates TradingView's B3 4h bars.
- Yahoo's 1h history is about 730 days, enough for the 4h SMA200.
- Differences are real. On 2026-10-09 the layer states matched on all 10 tickers tested, but the last arrow differed on 2 of them (for example PETR4: a close of 47.99 on MT5 against 48.07 on Yahoo put it on opposite sides of the SMA20 on 2026-09-25).

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
- **4h bars (layer 2).** MT5's own H4 bars are not used. They are rebuilt from 1-minute bars as two per day (10:00-13:59 and 14:00-close), **dropping the last 1-minute bar of each day**, which carries the closing auction. TradingView's 4h bars on B3 end on the last continuous-trading price, while the daily bar and MT5's H4 bars include the auction. Keeping it flipped two layer 2 days on USIM3; dropping it matched all 12 labeled days. This needs about 100 trading days of 1-minute history; if the broker has less, the MT5 source fails and `auto` falls back to Yahoo Finance.
- CSV exports of MT5 H4 bars cannot be fixed this way (the auction is already inside them), so `--source csv` keeps the older "merge the last two of three" approximation for 4h.
- Data from MT5 and TradingView can differ slightly (adjustments), so a close within a cent or two of an average can flip.
- Research tool, not financial advice.

## Tests

```bash
pip install pytest
python -m pytest tests
```
