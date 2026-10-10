import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
import pytest
import screener
from test_store import _frames


class Fake:
    """Provider that serves the same synthetic frames, optionally failing on chosen symbols."""

    def __init__(self, name, fail=()):
        self.name, self.fail, self.closed = name, set(fail), False

    def get(self, symbol, tf, bars):
        if symbol in self.fail:
            raise ValueError(f"no data for {symbol}")
        daily, w, h4 = _frames()
        return {"D1": daily, "W1": w, "H4": h4}[tf]

    def close(self):
        self.closed = True


def _unavailable():
    raise SystemExit("terminal not logged in")


def test_primary_used_when_it_has_every_symbol():
    p = Fake("mt5")
    name, res, err = screener.scan_all_or_nothing(lambda: p, lambda: Fake("yfinance"),
                                                  ["A3", "B3"], "live", False)
    assert name == "mt5" and set(res) == {"A3", "B3"} and not err and p.closed


def test_one_missing_symbol_sends_everything_to_the_fallback():
    name, res, err = screener.scan_all_or_nothing(lambda: Fake("mt5", fail={"B3"}), lambda: Fake("yfinance"),
                                                  ["A3", "B3"], "live", False)
    assert name == "yfinance" and set(res) == {"A3", "B3"} and not err


def test_primary_that_cannot_start_falls_back():
    name, res, err = screener.scan_all_or_nothing(_unavailable, lambda: Fake("yfinance"),
                                                  ["A3"], "live", False)
    assert name == "yfinance" and set(res) == {"A3"}


def test_fallback_errors_are_reported_not_hidden():
    name, res, err = screener.scan_all_or_nothing(_unavailable, lambda: Fake("yfinance", fail={"B3"}),
                                                  ["A3", "B3"], "live", False)
    assert name == "yfinance" and set(res) == {"A3"} and [s for s, _ in err] == ["B3"]
