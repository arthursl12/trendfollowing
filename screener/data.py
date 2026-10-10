"""Data providers. Each returns a DataFrame indexed by time with open/high/low/close columns."""
from __future__ import annotations
import glob
import os
import pandas as pd
from rules import h4_from_intraday

_TF_MT5 = {"D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1", "H4": "TIMEFRAME_H4"}


class MT5Provider:
    """Reads bars from a running MetaTrader 5 terminal (Windows only)."""

    name = "mt5"

    def __init__(self, path: str | None = None):
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise SystemExit("MetaTrader5 package not found. Install it with: pip install MetaTrader5 "
                             "(Windows only, and the MT5 terminal must be installed and logged in).") from e
        self.mt5 = mt5
        if not (mt5.initialize(path=path) if path else mt5.initialize()):
            raise SystemExit(f"Could not connect to the MT5 terminal: {mt5.last_error()}")

    def get(self, symbol: str, tf: str, bars: int) -> pd.DataFrame:
        mt5 = self.mt5
        mt5.symbol_select(symbol, True)  # make sure the symbol is in Market Watch
        if tf == "H4":
            return self._h4_from_m1(symbol, bars)
        rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, _TF_MT5[tf]), 0, bars)
        if rates is None or len(rates) == 0:
            raise ValueError(f"No {tf} data for {symbol}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df.set_index("time")[["open", "high", "low", "close"]]

    # MT5 caps one request around 60k bars. About 100 trading days are needed for the 4h SMA200,
    # and a 4h bar is built from ~420 one-minute bars, so 60k covers it with margin.
    _M1_BARS = 60_000
    _MIN_H4_BARS = 220

    def _h4_from_m1(self, symbol: str, bars: int) -> pd.DataFrame:
        """TradingView-like 4h bars from 1-minute data, without the closing auction (see rules.h4_from_intraday).

        MT5's own H4 bars (3 per day, auction included) gave wrong layer 2 days on USIM3.
        Raises if the broker has too little 1-minute history for a 4h SMA200, so an all-or-nothing
        caller can fall back to another source instead of silently turning layer 2 off.
        """
        mt5 = self.mt5
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, self._M1_BARS)
        if rates is None or len(rates) == 0:
            raise ValueError(f"No M1 data for {symbol}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        h4 = h4_from_intraday(df.set_index("time")[["open", "high", "low", "close"]], drop_last_bar=True)
        if len(h4) < self._MIN_H4_BARS:
            raise ValueError(f"Only {len(h4)} 4h bars for {symbol} from M1 history; need {self._MIN_H4_BARS}")
        return h4.tail(bars)

    def close(self):
        self.mt5.shutdown()


class YFinanceProvider:
    """Reads bars from Yahoo Finance (B3 tickers get the .SA suffix). Backup for when MT5 is not available.

    Differences from MT5 worth knowing:
      * prices are unadjusted closes, but Yahoo's history can still differ from the broker's;
      * Yahoo has no 4h bars, so they are built from 1h bars, two per day (10:00-13:59 and 14:00-close);
        its hourly bars end before the closing auction, like TradingView's 4h bars;
      * 1h history is limited to about 730 days.
    """

    name = "yfinance"

    def __init__(self):
        try:
            import yfinance
        except ImportError as e:
            raise SystemExit("yfinance package not found. Install it with: pip install yfinance") from e
        self.yf = yfinance

    @staticmethod
    def _ticker(symbol: str) -> str:
        return symbol if "." in symbol else f"{symbol}.SA"

    def _download(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        df = self.yf.download(self._ticker(symbol), period=period, interval=interval,
                              auto_adjust=False, progress=False, threads=False)
        if df is None or len(df) == 0:
            raise ValueError(f"No {interval} data for {self._ticker(symbol)} from Yahoo Finance")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
        df.index = pd.DatetimeIndex(df.index).tz_localize(None)
        return df

    def get(self, symbol: str, tf: str, bars: int) -> pd.DataFrame:
        if tf == "D1":
            return self._download(symbol, "1d", "max").tail(bars)
        if tf == "W1":
            return self._download(symbol, "1wk", "max").tail(bars)
        h1 = self._download(symbol, "1h", "730d")
        return h4_from_intraday(h1).tail(bars)

    def close(self):
        pass


class CsvProvider:
    """Reads MT5 'export bars' CSV files (tab separated), e.g. USIM3_Daily_*.csv, USIM3_H4_*.csv."""

    name = "csv"
    _NAME = {"D1": "Daily", "W1": "Weekly", "H4": "H4"}

    def __init__(self, folder: str):
        self.folder = folder

    def get(self, symbol: str, tf: str, bars: int) -> pd.DataFrame:
        pattern = os.path.join(self.folder, f"*{symbol}_{self._NAME[tf]}_*.csv")
        files = sorted(glob.glob(pattern))
        if not files and tf == "W1":
            # no weekly export: build weekly bars from the daily file (labelled by their Friday)
            d = self.get(symbol, "D1", 10_000)
            w = d.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            return w.dropna().tail(bars)
        if not files:
            raise ValueError(f"No file matching {pattern}")
        df = pd.read_csv(files[-1], sep="\t")
        df.columns = [c.strip("<>").lower() for c in df.columns]
        stamp = df["date"].astype(str) + (" " + df["time"].astype(str) if "time" in df else "")
        df.index = pd.to_datetime(stamp, format="mixed")
        return df[["open", "high", "low", "close"]].tail(bars)

    def close(self):
        pass
