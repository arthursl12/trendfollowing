# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A personal research project: a single TradingView Pine Script v6 indicator (`src/trend_pullback_study.pine`) that reproduces a closed-source trend/pullback chart setup, reconstructed by black-box observation on B3 daily data (BBAS3, PETR4, USIM3). `README.md` documents the method, findings, dead ends and roadmap (Python cross-check and `strategy()` backtest are planned, not built). It is a study, not a signal service or order executor.

There is no build, lint or test tooling. The script is run by pasting it into the TradingView Pine Editor and adding it to a daily B3 chart.

## Architecture (all in `src/trend_pullback_study.pine`)

- **Layer 1**: `bull`/`bear` = close above/below EMA9, SMA20 and SMA200 on the chart's own timeframe.
- **Arrows**: `pullbackUp`/`pullbackDown` = trend state now and previous close on the other side of the previous SMA20. Deliberately use only chart-timeframe data so they don't repaint and are safe to backtest.
- **Layer 2**: layer 1 AND the same trend rule holding on 4h, daily and weekly via `request.security()`. Drawn as a separate 90%-transparent `bgcolor` overlay so it stacks into a darker tint; there is no "strong/weak" grading. It repaints on the live bar.

## Constraints to preserve

- **Pine v6 `and` short-circuits.** Every `ta.*` call must be computed on its own line before any `and` chain (see `f_up()`/`f_down()`), otherwise its history gets gaps and values are silently wrong (this previously hid layer 2). Never inline `ta.*` inside a boolean expression.
- **No tunable lengths, on purpose** (9/20/200 fixed). Only visibility toggles are inputs; don't add parameters without a reason, since the fixed rule set is a stated design decision.
- **Rule changes are validated by falsification**: a rule is kept only if it explains every labeled bar. Check the README "Dead ends" table before re-trying an idea for layer 2.
- Keep arrows independent of layer 2.
