"""Trend + pullback rules, as pure functions on pandas data (no I/O).

Mirrors the Pine study:
  layer 1 : close above (below) EMA9, SMA20 and SMA200
  arrows  : layer 1 now, previous close on the other side of the previous SMA20
  layer 2 : layer 1 AND the same trend rule holds on 4h, daily and weekly
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def trend_flags(close: pd.Series, allow_short_history: bool = False) -> pd.DataFrame:
    """Return ema9, sma20, sma200 and the up/down trend flags for a close series.

    allow_short_history: treat a missing SMA200 (not enough bars) as satisfied.
    Only meant for validation on short samples. Leave it off for real screening.
    """
    ema9 = close.ewm(span=9, adjust=False).mean()
    sma20 = close.rolling(20).mean()
    sma200 = close.rolling(200).mean()
    ok200_up = (close > sma200) | (sma200.isna() if allow_short_history else False)
    ok200_dn = (close < sma200) | (sma200.isna() if allow_short_history else False)
    up = (close > ema9) & (close > sma20) & ok200_up
    dn = (close < ema9) & (close < sma20) & ok200_dn
    return pd.DataFrame({"close": close, "ema9": ema9, "sma20": sma20, "sma200": sma200,
                         "up": up.fillna(False).astype(bool),
                         "dn": dn.fillna(False).astype(bool)})


def pullbacks(f: pd.DataFrame) -> pd.DataFrame:
    """Arrows: trend now, and the previous close was on the other side of the previous SMA20."""
    pb_up = f["up"] & (f["close"].shift(1) < f["sma20"].shift(1))
    pb_dn = f["dn"] & (f["close"].shift(1) > f["sma20"].shift(1))
    return pd.DataFrame({"pb_up": pb_up.fillna(False), "pb_dn": pb_dn.fillna(False)})


def merge_h4(h4: pd.DataFrame) -> pd.DataFrame:
    """MT5 H4 bars on B3 come as 3 per day (08:00, 12:00, 16:00).

    TradingView's 4h chart on B3 has 2 per day, so the last two MT5 bars of a day
    are merged into one. Days that do not have exactly 3 bars are left unchanged.
    """
    out = []
    for _, day in h4.sort_index().groupby(h4.index.date):
        if len(day) == 3:
            a, b, c = day.iloc[0], day.iloc[1], day.iloc[2]
            merged = pd.Series({"open": b["open"], "high": max(b["high"], c["high"]),
                                "low": min(b["low"], c["low"]), "close": c["close"]},
                               name=day.index[1])
            out.append(a[["open", "high", "low", "close"]].rename(day.index[0]))
            out.append(merged)
        else:
            for ts, r in day.iterrows():
                out.append(r[["open", "high", "low", "close"]].rename(ts))
    return pd.DataFrame(out)


def h4_state_per_day(h4: pd.DataFrame, allow_short_history: bool = False) -> pd.DataFrame:
    """4h trend flags, sampled at the last 4h bar of each day."""
    f = trend_flags(merge_h4(h4)["close"], allow_short_history)
    last = f[["up", "dn"]].groupby(f.index.date).last()
    last.index = pd.to_datetime(last.index)
    return last


def _week_end(ts: pd.Timestamp) -> pd.Timestamp:
    """Friday of the week that contains (or follows) ts. A Sunday/Monday week label maps to its Friday."""
    return pd.offsets.Week(weekday=4).rollforward(ts.normalize())


def weekly_state_on_daily(daily_index: pd.DatetimeIndex, w1: pd.DataFrame,
                          mode: str = "completed", allow_short_history: bool = False) -> pd.DataFrame:
    """Map weekly trend flags onto daily bars the way TradingView does with lookahead off.

    completed: a daily bar sees the weekly value of the last COMPLETED week, except on the
               last trading day of a week, where it sees that week's final value.
    live     : same, but the very last daily bar uses the developing weekly bar
               (what a live chart shows today).
    """
    f = trend_flags(w1["close"], allow_short_history)
    f.index = [_week_end(t) for t in f.index]
    f = f[~f.index.duplicated(keep="last")]
    wk = pd.Series([_week_end(t) for t in daily_index], index=daily_index)
    last_day = pd.Series(daily_index, index=daily_index).groupby(wk).transform("max")
    prev_end = wk - pd.Timedelta(days=7)
    res = {}
    for col in ("up", "dn"):
        cur = wk.map(f[col])
        prev = prev_end.map(f[col])
        v = np.where(daily_index == last_day.values, cur, prev)
        if mode == "live" and len(daily_index):
            v[-1] = cur.iloc[-1]
        res[col] = pd.Series(v, index=daily_index).fillna(False).astype(bool)
    return pd.DataFrame(res)


def analyze(daily: pd.DataFrame, w1: pd.DataFrame, h4: pd.DataFrame,
            weekly_mode: str = "live", allow_short_history: bool = False) -> pd.DataFrame:
    """Full per-day table: layer 1, arrows and layer 2 for one symbol."""
    d = trend_flags(daily["close"], allow_short_history)
    d = d.join(pullbacks(d))
    w = weekly_state_on_daily(d.index, w1, weekly_mode, allow_short_history)
    h = h4_state_per_day(h4, allow_short_history).reindex(d.index)
    h = h.fillna(False).astype(bool)
    d["l2_up"] = d["up"] & h["up"] & w["up"]
    d["l2_dn"] = d["dn"] & h["dn"] & w["dn"]
    return d
