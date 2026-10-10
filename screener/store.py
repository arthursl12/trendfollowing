"""SQLite snapshot store: what the screener saw on each run, so the dashboard never recomputes.

Two tables
  bars      per-symbol daily history (last KEEP_BARS rows), replaced on every ingest
  snapshots one summary row per (as-of date, symbol), kept, so day-over-day changes are a lookup
"""
from __future__ import annotations
import sqlite3
import pandas as pd

KEEP_BARS = 260

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    close REAL, ema9 REAL, sma20 REAL, sma200 REAL,
    up INTEGER, dn INTEGER, pb_up INTEGER, pb_dn INTEGER, l2_up INTEGER, l2_dn INTEGER,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS snapshots (
    asof TEXT NOT NULL, symbol TEXT NOT NULL,
    close REAL, trend_l1 TEXT, trend_l2 TEXT, pullback_today TEXT,
    bars_since_pullback INTEGER, last_pullback TEXT, dist_sma20_pct REAL,
    PRIMARY KEY (asof, symbol)
);
"""

BAR_COLS = ["close", "ema9", "sma20", "sma200", "up", "dn", "pb_up", "pb_dn", "l2_up", "l2_dn"]
FLAG_COLS = ["up", "dn", "pb_up", "pb_dn", "l2_up", "l2_dn"]


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _num(v):
    return None if pd.isna(v) else float(v)


def save(conn: sqlite3.Connection, symbol: str, table: pd.DataFrame, summary: dict) -> None:
    """Store one symbol's run: replace its bars and upsert today's snapshot row.

    `table` is the output of rules.analyze(); `summary` is screener.summarize() for the same run.
    Re-running on the same as-of date overwrites that day's snapshot (the live bar can still move).
    """
    rows = []
    for ts, r in table.tail(KEEP_BARS).iterrows():
        vals = [_num(r[c]) if c not in FLAG_COLS else int(bool(r[c])) for c in BAR_COLS]
        rows.append((symbol, ts.date().isoformat(), *vals))
    with conn:
        conn.execute("DELETE FROM bars WHERE symbol = ?", (symbol,))
        conn.executemany(f"INSERT INTO bars VALUES (?, ?, {', '.join('?' * len(BAR_COLS))})", rows)
        conn.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (summary["date"], symbol, summary["close"], summary["trend_L1"], summary["trend_L2"],
             summary["pullback_today"], summary["bars_since_pullback"], summary["last_pullback"],
             summary["dist_sma20_pct"]))


def latest_asof(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(asof) FROM snapshots").fetchone()
    return row[0]


def _change_list(cur: sqlite3.Row, prev: sqlite3.Row | None) -> list[dict]:
    out = []
    if cur["pullback_today"] != "-":
        out.append({"kind": "arrow", "text": f"Arrow {cur['pullback_today']}"})
    if prev is not None:
        for kind, col, label in (("l2", "trend_l2", "L2"), ("l1", "trend_l1", "L1")):
            if cur[col] != prev[col]:
                was = "none" if prev[col] == "-" else prev[col]
                now = "none" if cur[col] == "-" else cur[col]
                out.append({"kind": kind, "text": f"{label} {was} → {now}"})
    return out


def snapshot_with_changes(conn: sqlite3.Connection, asof: str | None = None) -> list[dict]:
    """Snapshot rows for `asof` (default: latest), each with the changes since the symbol's
    previous stored snapshot. A symbol with no earlier snapshot reports no L1/L2 changes."""
    asof = asof or latest_asof(conn)
    if asof is None:
        return []
    out = []
    for cur in conn.execute("SELECT * FROM snapshots WHERE asof = ? ORDER BY symbol", (asof,)):
        prev = conn.execute(
            "SELECT * FROM snapshots WHERE symbol = ? AND asof < ? ORDER BY asof DESC LIMIT 1",
            (cur["symbol"], asof)).fetchone()
        d = dict(cur)
        d["prev_asof"] = prev["asof"] if prev else None
        d["changes"] = _change_list(cur, prev)
        out.append(d)
    return out


def bars_for(conn: sqlite3.Connection, symbol: str, n: int) -> list[list]:
    """Last n bars as compact rows: [date, close, ema9, sma20, sma200, up, dn, pb_up, pb_dn, l2_up, l2_dn]."""
    rows = conn.execute(
        f"SELECT date, {', '.join(BAR_COLS)} FROM bars WHERE symbol = ? ORDER BY date DESC LIMIT ?",
        (symbol, n)).fetchall()
    return [list(r) for r in reversed(rows)]
