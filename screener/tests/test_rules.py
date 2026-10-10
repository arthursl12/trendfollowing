import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import numpy as np
import pandas as pd
from rules import trend_flags, pullbacks, merge_h4, weekly_state_on_daily


def _series(values, start="2024-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_steady_uptrend_is_up_and_not_down():
    f = trend_flags(_series(np.linspace(10, 40, 300)))
    assert f["up"].iloc[-1] and not f["dn"].iloc[-1]


def test_steady_downtrend_is_down_and_not_up():
    f = trend_flags(_series(np.linspace(40, 10, 300)))
    assert f["dn"].iloc[-1] and not f["up"].iloc[-1]


def test_needs_200_bars_unless_short_history_allowed():
    s = _series(np.linspace(10, 20, 100))
    assert not trend_flags(s)["up"].any()
    assert trend_flags(s, allow_short_history=True)["up"].iloc[-1]


def test_pullback_up_fires_on_first_bar_back_in_trend():
    base = list(np.linspace(10, 30, 250))
    dip = [base[-1] - 8]            # drops under SMA20 (and the others)
    back = [base[-1] + 4]           # jumps back above all three
    f = trend_flags(_series(base + dip + back))
    pb = pullbacks(f)
    assert pb["pb_up"].iloc[-1]
    assert not pb["pb_up"].iloc[-2]  # the dip bar itself is not a pullback signal


def test_merge_h4_merges_last_two_of_three_bars():
    idx = pd.to_datetime(["2026-01-05 08:00", "2026-01-05 12:00", "2026-01-05 16:00"])
    h4 = pd.DataFrame({"open": [1, 2, 3], "high": [5, 6, 9], "low": [0, 1, 2], "close": [2, 3, 4]}, index=idx)
    m = merge_h4(h4)
    assert len(m) == 2
    assert m.iloc[1]["open"] == 2 and m.iloc[1]["high"] == 9 and m.iloc[1]["low"] == 1 and m.iloc[1]["close"] == 4


def test_weekly_value_updates_only_on_last_day_of_week():
    # two weeks of daily bars; week 1 is "up", week 2 is "down"
    daily = pd.bdate_range("2026-01-05", "2026-01-16")                    # Mon..Fri x2
    w1 = pd.DataFrame({"close": [10.0, 5.0]}, index=pd.to_datetime(["2026-01-04", "2026-01-11"]))
    # hand-made flags: bypass indicators by using allow_short_history and monotone data
    res = weekly_state_on_daily(daily, w1, "completed", allow_short_history=True)
    # first week has no previous completed week: False until Friday
    assert not res["up"].iloc[0:4].any()
    assert list(res.columns) == ["up", "dn"]


def test_h4_from_intraday_two_bars_per_day_and_drops_auction_bar():
    from rules import h4_from_intraday
    idx = pd.to_datetime(["2026-09-21 10:05", "2026-09-21 13:59", "2026-09-21 14:00", "2026-09-21 16:50",
                          "2026-09-21 16:54"])
    m1 = pd.DataFrame({"open": [6.0, 6.1, 6.2, 6.5, 6.5], "high": [6.1, 6.2, 6.3, 6.6, 6.7],
                       "low": [5.9, 6.0, 6.1, 6.4, 6.4], "close": [6.1, 6.2, 6.3, 6.51, 6.61]}, index=idx)
    keep = h4_from_intraday(m1)
    assert list(keep.index.hour) == [10, 14] and keep["close"].iloc[-1] == 6.61
    drop = h4_from_intraday(m1, drop_last_bar=True)
    assert drop["close"].iloc[-1] == 6.51 and drop["high"].iloc[-1] == 6.6
    assert drop["open"].iloc[0] == 6.0 and drop["close"].iloc[0] == 6.2
