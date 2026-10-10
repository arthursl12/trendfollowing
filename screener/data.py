"""Data providers. Each returns a DataFrame indexed by time with open/high/low/close columns."""
from __future__ import annotations
import glob
import os
import pandas as pd

_TF_MT5 = {"D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1", "H4": "TIMEFRAME_H4"}


class MT5Provider:
    """Reads bars from a running MetaTrader 5 terminal (Windows only)."""

    def __init__(self):
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise SystemExit("MetaTrader5 package not found. Install it with: pip install MetaTrader5 "
                             "(Windows only, and the MT5 terminal must be installed and logged in).") from e
        self.mt5 = mt5
        if not mt5.initialize():
            raise SystemExit(f"Could not connect to the MT5 terminal: {mt5.last_error()}")

    def get(self, symbol: str, tf: str, bars: int) -> pd.DataFrame:
        mt5 = self.mt5
        mt5.symbol_select(symbol, True)  # make sure the symbol is in Market Watch
        rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, _TF_MT5[tf]), 0, bars)
        if rates is None or len(rates) == 0:
            raise ValueError(f"No {tf} data for {symbol}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df.set_index("time")[["open", "high", "low", "close"]]

    def close(self):
        self.mt5.shutdown()


class CsvProvider:
    """Reads MT5 'export bars' CSV files (tab separated), e.g. USIM3_Daily_*.csv, USIM3_H4_*.csv."""

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
