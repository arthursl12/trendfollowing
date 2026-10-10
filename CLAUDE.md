# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A personal research project: a single TradingView Pine Script v6 indicator (`src/trend_pullback_study.pine`) that reproduces a closed-source trend/pullback chart setup, reconstructed by black-box observation on B3 daily data (BBAS3, PETR4, USIM3). `README.md` documents the method, findings, dead ends and roadmap. A Python port of the rules and an MT5 screener live in `screener/`; the `strategy()` backtest is planned, not built. It is a study, not a signal service or order executor.

There is no build or lint tooling. The Pine script is run by pasting it into the TradingView Pine Editor and adding it to a daily B3 chart. The Python screener has pytest tests: `cd screener && python -m pytest tests` (needs pandas, numpy, pytest; MetaTrader5 is Windows-only and only needed for `--source mt5`).

## Architecture (all in `src/trend_pullback_study.pine`)

- **Layer 1**: `bull`/`bear` = close above/below EMA9, SMA20 and SMA200 on the chart's own timeframe.
- **Arrows**: `pullbackUp`/`pullbackDown` = trend state now and previous close on the other side of the previous SMA20. Deliberately use only chart-timeframe data so they don't repaint and are safe to backtest.
- **Layer 2**: layer 1 AND the same trend rule holding on 4h, daily and weekly via `request.security()`. Drawn as a separate 90%-transparent `bgcolor` overlay so it stacks into a darker tint; there is no "strong/weak" grading. It repaints on the live bar.

## Python screener (`screener/`)

- `rules.py` is a pure-pandas mirror of the Pine rules (no I/O); `data.py` has the MT5 and CSV providers; `screener.py` is the CLI.
- **The Pine script is the source of truth.** Any rule change goes into the Pine first, then `rules.py`, and the tests must stay green.
- The same 9/20/200 fixed-length and "arrows independent of layer 2" constraints below apply to the port.
- `store.py` (SQLite snapshots, day-over-day changes) and `report.py` (static HTML dashboard) sit on top of the screener. `--source auto` uses MT5 and, if it cannot deliver every symbol, Yahoo Finance for all of them; a screen never mixes sources.
- 4h bars (layer 2) are rebuilt from 1-minute (MT5) or 1-hour (Yahoo) bars as two per day with the closing auction excluded, because TradingView's B3 4h bars do not include it (`rules.h4_from_intraday`). MT5's native H4 bars gave wrong layer 2 days. Weekly values are mapped onto daily bars to imitate `request.security()` with lookahead off.
- Validated against TradingView labeled bars on USIM3 only (12 days, 2026-09-15 to 09-30, all matching). Layer 1 and arrows on BBAS3 and PETR4 are validated in the Pine study, not yet for the Python port.

## Constraints to preserve

- **Pine v6 `and` short-circuits.** Every `ta.*` call must be computed on its own line before any `and` chain (see `f_up()`/`f_down()`), otherwise its history gets gaps and values are silently wrong (this previously hid layer 2). Never inline `ta.*` inside a boolean expression.
- **No tunable lengths, on purpose** (9/20/200 fixed). Only visibility toggles are inputs; don't add parameters without a reason, since the fixed rule set is a stated design decision.
- **Rule changes are validated by falsification**: a rule is kept only if it explains every labeled bar. Check the README "Dead ends" table before re-trying an idea for layer 2.
- Keep arrows independent of layer 2.
