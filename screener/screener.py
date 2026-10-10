"""Daily screener for the trend + pullback study.

Examples
  python screener.py --symbols PETR4 VALE3 BBAS3            (auto: MT5, else Yahoo Finance for all)
  python screener.py --source mt5 --symbols PETR4 VALE3 BBAS3
  python screener.py --source yfinance --symbols PETR4 VALE3
  python screener.py --source mt5 --symbols-file tickers.txt --out results.csv
  python screener.py --source csv --folder ./exports --symbols USIM3 --weekly-mode completed --allow-short-history
"""
from __future__ import annotations
import argparse
import pandas as pd
from data import MT5Provider, CsvProvider, YFinanceProvider
from rules import analyze
import store


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


def scan(src, symbols, weekly_mode, allow_short_history):
    """Analyze every symbol with one provider. Returns ({symbol: table}, [(symbol, error)])."""
    results, errors = {}, []
    for s in symbols:
        try:
            results[s] = analyze(src.get(s, "D1", 800), src.get(s, "W1", 400), src.get(s, "H4", 4000),
                                 weekly_mode, allow_short_history)
        except Exception as e:  # keep scanning the other symbols
            errors.append((s, str(e)))
    return results, errors


def scan_all_or_nothing(make_primary, make_fallback, symbols, weekly_mode, allow_short_history):
    """Use the primary provider only if it delivers EVERY symbol; otherwise redo all with the fallback.

    A screen never mixes sources: its numbers differ slightly between vendors, so a half-and-half
    table could not be compared with itself. Returns (source name, results, errors).
    """
    try:
        primary = make_primary()
    except SystemExit as e:  # provider could not start (package missing, terminal not logged in)
        print(f"[fallback] primary source unavailable: {e}")
        primary = None
    if primary is not None:
        try:
            results, errors = scan(primary, symbols, weekly_mode, allow_short_history)
        finally:
            primary.close()
        if results and not errors:
            return primary.name, results, errors
        print(f"[fallback] {primary.name} missed {len(errors)} of {len(symbols)} symbols"
              + (f" ({errors[0][0]}: {errors[0][1]})" if errors else "") + "; using the fallback for all")
    fb = make_fallback()
    try:
        results, errors = scan(fb, symbols, weekly_mode, allow_short_history)
    finally:
        fb.close()
    return fb.name, results, errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["auto", "mt5", "yfinance", "csv"], default="auto",
                   help="auto = MT5, and Yahoo Finance for ALL symbols if MT5 is unavailable or misses any")
    p.add_argument("--mt5-path", help="full path to terminal64.exe (when several MT5 terminals are installed)")
    p.add_argument("--folder", help="folder with exported CSVs (csv source)")
    p.add_argument("--symbols", nargs="*", default=[])
    p.add_argument("--symbols-file", help="text file with one ticker per line")
    p.add_argument("--out", help="write results to this CSV")
    p.add_argument("--db", help="SQLite file to store bars and today's snapshot (feeds report.py)")
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

    scan_args = (symbols, a.weekly_mode, a.allow_short_history)
    if a.source == "auto":
        source, results, errors = scan_all_or_nothing(
            lambda: MT5Provider(a.mt5_path), YFinanceProvider, *scan_args)
    else:
        make = {"mt5": lambda: MT5Provider(a.mt5_path), "yfinance": YFinanceProvider,
                "csv": lambda: CsvProvider(a.folder or ".")}[a.source]
        src = make()
        try:
            results, errors = scan(src, *scan_args)
        finally:
            src.close()
        source = src.name
    print(f"[source] {source}" + ("" if a.source != "auto" else " (auto: MT5 first, Yahoo Finance as all-or-nothing backup)"))

    if a.history:
        if not results:
            raise SystemExit(f"{a.history}: {errors[0][1] if errors else 'no data'}")
        t = results[a.history]
        print(t[["close", "up", "dn", "pb_up", "pb_dn", "l2_up", "l2_dn"]].to_string())
        return

    conn = store.connect(a.db) if a.db else None
    rows = []
    try:
        for s, t in results.items():
            row = summarize(s, t)
            rows.append(row)
            if conn:
                store.save(conn, s, t, row, source)
    finally:
        if conn:
            conn.close()

    if rows:
        df = pd.DataFrame(rows).sort_values(["pullback_today", "trend_L2", "trend_L1"], ascending=False)
        print(df.to_string(index=False))
        if a.out:
            df.to_csv(a.out, index=False)
    for s, e in errors:
        print(f"[skipped] {s}: {e}")


if __name__ == "__main__":
    main()
