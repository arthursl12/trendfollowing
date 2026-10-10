import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np
import pandas as pd
import pytest
import report
import store
from rules import analyze
from screener import summarize


def _frames(n_days=900, seed=0, drift=0.001):
    rng = np.random.default_rng(seed)
    d = pd.bdate_range("2021-01-04", periods=n_days)
    c = 20 * np.exp(np.cumsum(rng.normal(drift, 0.015, n_days)))
    daily = pd.DataFrame({"open": c, "high": c, "low": c, "close": c}, index=d)
    w = daily.resample("W-FRI").last().dropna()
    h4 = pd.DataFrame([(ts.replace(hour=h), v, v, v, v) for ts, v in zip(d, c) for h in (8, 12, 16)],
                      columns=["time", "open", "high", "low", "close"]).set_index("time")
    return daily, w, h4


def _run(conn, symbol, **kw):
    t = analyze(*_frames(**kw))
    store.save(conn, symbol, t, summarize(symbol, t))
    return t


def test_save_and_load_roundtrip(tmp_path):
    conn = store.connect(str(tmp_path / "s.db"))
    t = _run(conn, "AAA3")
    rows = store.snapshot_with_changes(conn)
    assert [r["symbol"] for r in rows] == ["AAA3"]
    assert rows[0]["asof"] == t.index[-1].date().isoformat()
    bars = store.bars_for(conn, "AAA3", 50)
    assert len(bars) == 50 and bars[-1][0] == rows[0]["asof"]


def test_rerun_same_day_overwrites_instead_of_duplicating(tmp_path):
    conn = store.connect(str(tmp_path / "s.db"))
    _run(conn, "AAA3"); _run(conn, "AAA3")
    assert conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM bars WHERE symbol='AAA3'").fetchone()[0] == store.KEEP_BARS


def test_changes_compare_with_previous_stored_snapshot(tmp_path):
    conn = store.connect(str(tmp_path / "s.db"))
    for asof, l1, l2, pb in (("2026-01-02", "UP", "UP", "-"), ("2026-01-05", "UP", "-", "-"),
                             ("2026-01-06", "-", "-", "UP")):
        conn.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (asof, "AAA3", 10.0, l1, l2, pb, 3, "2026-01-01", 1.0, None))
    r = store.snapshot_with_changes(conn, "2026-01-05")[0]
    assert r["prev_asof"] == "2026-01-02"
    assert [c["text"] for c in r["changes"]] == ["L2 UP → none"]
    r = store.snapshot_with_changes(conn, "2026-01-06")[0]
    assert {c["kind"] for c in r["changes"]} == {"arrow", "l1"}
    first = store.snapshot_with_changes(conn, "2026-01-02")[0]
    assert first["prev_asof"] is None and first["changes"] == []


def test_report_embeds_valid_json_and_escapes_markup(tmp_path):
    conn = store.connect(str(tmp_path / "s.db"))
    t = analyze(*_frames())
    row = summarize("EVIL</script>3", t)
    store.save(conn, "EVIL</script>3", t, row)
    conn.close()
    html = report.build(str(tmp_path / "s.db"), n_bars=30)
    assert html.count("</script>") == 2  # the data block and the app script, nothing injected
    payload = re.search(r'id="data">(.*?)</script>', html, re.S).group(1)
    data = json.loads(payload)
    assert data["rows"][0]["symbol"] == "EVIL</script>3"
    assert len(data["bars"]["EVIL</script>3"]) == 30


def test_report_without_snapshots_exits(tmp_path):
    store.connect(str(tmp_path / "e.db")).close()
    with pytest.raises(SystemExit):
        report.build(str(tmp_path / "e.db"))


def test_changes_flag_a_source_switch(tmp_path):
    conn = store.connect(str(tmp_path / "s.db"))
    for asof, src in (("2026-01-02", "mt5"), ("2026-01-05", "yfinance")):
        conn.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (asof, "AAA3", 10.0, "UP", "UP", "-", 3, "2026-01-01", 1.0, src))
    r = store.snapshot_with_changes(conn, "2026-01-05")[0]
    assert [(c["kind"], c["text"]) for c in r["changes"]] == [("source", "Source mt5 → yfinance")]


def test_old_database_without_source_column_is_migrated(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE snapshots (asof TEXT, symbol TEXT, close REAL, trend_l1 TEXT, trend_l2 TEXT, "
                "pullback_today TEXT, bars_since_pullback INTEGER, last_pullback TEXT, dist_sma20_pct REAL, "
                "PRIMARY KEY (asof, symbol))")
    raw.commit(); raw.close()
    conn = store.connect(path)
    assert "source" in {r[1] for r in conn.execute("PRAGMA table_info(snapshots)")}
