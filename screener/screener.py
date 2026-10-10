"""Daily screener for the trend + pullback study.

Examples
  python screener.py --source mt5 --symbols PETR4 VALE3 BBAS3
  python screener.py --source mt5 --symbols-file tickers.txt --out results.csv
  python screener.py --source csv --folder ./exports --symbols USIM3 --weekly-mode completed --allow-short-history
"""
from __future__ import annotations
import argparse
import pandas as pd
from data import MT5Provider, CsvProvider
from rules import analyze


def summarize(symbol: str, t: pd.DataFrame) -> dict:
    last = t.iloc[-1]
    arrow = t.index[t["pb_up"] | t["pb_dn"]]
    since = None
    if len(arrow):
        since = int((t.index > arrow[-1]).sum())
    state = "UP" if last["up"] else "DOWN" if last["dn"] else "-"
    l2 = "UP" if last["l2_up"] else "DOWN" if last["l2_dn"] else "-"
    pullback = "UP" if last["pb_up"] else "DOWN" if last["pb_dn"] else "-"
    return {
        "symbol": symbol, "date": t.index[-1].date().isoformat(), "close": round(float(last["close"]), 2),
        "trend_L1": state, "trend_L2": l2, "pullback_today": pullback,
        "bars_since_pullback": since,
        "last_pullback": arrow[-1].date().isoformat() if len(arrow) else None,
        "dist_sma20_pct": round(float((last["close"] / last["sma20"] - 1) * 100), 2),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["mt5", "csv"], default="mt5")
    p.add_argument("--folder", help="folder with exported CSVs (csv source)")
    p.add_argument("--symbols", nargs="*", default=[])
    p.add_argument("--symbols-file", help="text file with one ticker per line")
    p.add_argument("--out", help="write results to this CSV")
    p.add_argument("--weekly-mode", choices=["live", "completed"], default="live")
    p.add_argument("--allow-short-history", action="store_true",
                   help="ignore a missing SMA200 (validation on short samples only)")
    p.add_argument("--history", help="print the full per-day table for one symbol")
    a = p.parse_args()

    symbols = list(a.symbols)
    if a.symbols_file:
        symbols += [s.strip() for s in open(a.symbols_file) if s.strip() and not s.startswith("#")]
    if a.history:
        symbols = [a.history]
    if not symbols:
        raise SystemExit("Give --symbols or --symbols-file")

    src = MT5Provider() if a.source == "mt5" else CsvProvider(a.folder or ".")
    rows, errors = [], []
    try:
        for s in symbols:
            try:
                t = analyze(src.get(s, "D1", 800), src.get(s, "W1", 400), src.get(s, "H4", 4000),
                            a.weekly_mode, a.allow_short_history)
            except Exception as e:  # keep scanning the other symbols
                errors.append((s, str(e)))
                continue
            if a.history:
                print(t[["close", "up", "dn", "pb_up", "pb_dn", "l2_up", "l2_dn"]].to_string())
                return
            rows.append(summarize(s, t))
    finally:
        src.close()

    if rows:
        df = pd.DataFrame(rows).sort_values(["pullback_today", "trend_L2", "trend_L1"], ascending=False)
        print(df.to_string(index=False))
        if a.out:
            df.to_csv(a.out, index=False)
    for s, e in errors:
        print(f"[skipped] {s}: {e}")


if __name__ == "__main__":
    main()
