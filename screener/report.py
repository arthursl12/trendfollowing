"""Render the latest snapshot as one self-contained HTML file (no server, no network).

  python report.py --db screener.db --out report.html
"""
from __future__ import annotations
import argparse
import json
import store

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trend + Pullback screen</title>
<style>
  :root {
    color-scheme: light;
    --page: #f9f9f7; --surface: #fcfcfb;
    --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,.10); --wash: rgba(11,11,11,.05);
    --up: #2a78d6; --down: #e34948;
    --ema9: #eb6834; --sma20: #1baf7a; --sma200: #6250d6;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) {
      color-scheme: dark;
      --page: #0d0d0d; --surface: #1a1a19;
      --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,.10); --wash: rgba(255,255,255,.06);
      --up: #3987e5; --down: #e66767;
      --ema9: #d95926; --sma20: #199e70; --sma200: #9085e9;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,.10); --wash: rgba(255,255,255,.06);
    --up: #3987e5; --down: #e66767;
    --ema9: #d95926; --sma20: #199e70; --sma200: #9085e9;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--page); color: var(--ink);
         font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width: 1040px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { font-size: 20px; margin: 0 0 4px; font-weight: 600; }
  .sub { color: var(--ink-2); margin: 0 0 16px; }
  .filters { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; margin: 0 0 12px; }
  .seg { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .seg button { background: var(--surface); color: var(--ink-2); border: 0; padding: 6px 12px;
                font: inherit; cursor: pointer; }
  .seg button + button { border-left: 1px solid var(--border); }
  .seg button[aria-pressed="true"] { background: var(--wash); color: var(--ink); font-weight: 600; }
  .filters label { color: var(--ink-2); display: inline-flex; gap: 6px; align-items: center; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--grid); white-space: nowrap; }
  th { color: var(--muted); font-weight: 500; font-size: 12px; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.group td { background: var(--wash); color: var(--ink-2); font-size: 12px; font-weight: 600;
                text-transform: uppercase; letter-spacing: .04em; }
  tr.row:hover { background: var(--wash); }
  .sym { background: none; border: 0; padding: 0; font: inherit; font-weight: 600; color: var(--ink);
         cursor: pointer; text-decoration: underline; text-decoration-color: var(--axis); text-underline-offset: 3px; }
  .sym:focus-visible, .seg button:focus-visible { outline: 2px solid var(--up); outline-offset: 2px; }
  .chip { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 600;
          border: 1px solid transparent; }
  .chip.none { color: var(--muted); font-weight: 400; }
  .chip.up { background: color-mix(in srgb, var(--up) 14%, transparent); }
  .chip.down { background: color-mix(in srgb, var(--down) 14%, transparent); }
  .chip.strong.up { background: color-mix(in srgb, var(--up) 30%, transparent); border-color: var(--up); }
  .chip.strong.down { background: color-mix(in srgb, var(--down) 30%, transparent); border-color: var(--down); }
  .chip .ico { margin-right: 4px; }
  .chip.up .ico { color: var(--up); } .chip.down .ico { color: var(--down); }
  .badge { display: inline-block; margin-right: 6px; padding: 0 6px; border-radius: 4px; font-size: 12px;
           border: 1px solid var(--axis); color: var(--ink-2); }
  .badge.arrow { border-color: var(--ink); color: var(--ink); font-weight: 600; }
  .detail td { padding: 12px; background: var(--surface); }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 16px; color: var(--ink-2); font-size: 12px; margin: 0 0 8px; }
  .key { display: inline-block; width: 16px; height: 0; border-top: 2px solid; vertical-align: middle; margin-right: 6px; }
  .chartwrap { position: relative; }
  svg { display: block; width: 100%; height: auto; }
  .tip { position: absolute; pointer-events: none; background: var(--surface); border: 1px solid var(--border);
         border-radius: 8px; padding: 8px 10px; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.12);
         min-width: 150px; z-index: 2; }
  .tip b { font-weight: 600; }
  .tip .date { color: var(--ink-2); margin-bottom: 4px; }
  .tip .r { display: flex; justify-content: space-between; gap: 12px; }
  .tip .r span:first-child { color: var(--ink-2); }
  details { margin-top: 8px; color: var(--ink-2); font-size: 12px; }
  details table { font-size: 12px; margin-top: 6px; }
  details th, details td { padding: 3px 8px; }
  .scroll { max-height: 220px; overflow: auto; }
  .empty { padding: 24px; color: var(--ink-2); }
  .foot { color: var(--muted); font-size: 12px; margin-top: 16px; }
</style>
</head>
<body>
<main>
  <h1>Trend + Pullback screen</h1>
  <p class="sub" id="sub"></p>
  <div class="filters">
    <div class="seg" role="group" aria-label="Trend filter" id="trendFilter">
      <button data-v="all" aria-pressed="true">All</button>
      <button data-v="UP" aria-pressed="false">Up</button>
      <button data-v="DOWN" aria-pressed="false">Down</button>
    </div>
    <label><input type="checkbox" id="changedOnly"> Changed since previous run only</label>
  </div>
  <div class="card"><table id="tbl"></table></div>
  <p class="foot">Research tool, not financial advice. Layer 2 repaints on the live bar: read it after the close.</p>
</main>
<script type="application/json" id="data">__DATA__</script>
<script>
(() => {
const D = JSON.parse(document.getElementById('data').textContent);
const NS = 'http://www.w3.org/2000/svg';
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const el = (tag, props, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else e.setAttribute(k, v);
  }
  kids.forEach(k => k && e.append(k));
  return e;
};
const svg = (tag, attrs) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
};
const fmt = (v, d = 2) => v == null ? '–' : v.toFixed(d);

const state = { trend: 'all', changedOnly: false, open: null };
const GROUPS = [
  ['Arrow today', r => r.pullback_today !== '-'],
  ['Layer 2 aligned', r => r.trend_l2 !== '-'],
  ['Layer 1 trend', r => r.trend_l1 !== '-'],
  ['No trend', () => true],
];

function chip(v, strong) {
  if (v === '-') return el('span', { class: 'chip none', text: '–' });
  const up = v === 'UP';
  const c = el('span', { class: `chip ${up ? 'up' : 'down'}${strong ? ' strong' : ''}` },
    el('span', { class: 'ico', 'aria-hidden': 'true', text: up ? '▲' : '▼' }));
  c.append(up ? 'Up' : 'Down');
  return c;
}

function render() {
  const tbl = document.getElementById('tbl');
  tbl.replaceChildren();
  const head = el('tr');
  [['Symbol', ''], ['Close', 'num'], ['Layer 1', ''], ['Layer 2', ''], ['Arrow today', ''],
   ['Bars since arrow', 'num'], ['Dist. SMA20', 'num'], ['Changes', '']].forEach(([t, c]) =>
    head.append(el('th', { class: c, scope: 'col', text: t })));
  tbl.append(el('thead', {}, head));
  const body = el('tbody');
  let rows = D.rows.filter(r =>
    (state.trend === 'all' || r.trend_l1 === state.trend) && (!state.changedOnly || r.changes.length));
  if (!rows.length) {
    document.getElementById('tbl').replaceChildren(el('tbody', {}, el('tr', {},
      el('td', { class: 'empty', text: 'No symbols match the current filters.' }))));
    return;
  }
  const used = new Set();
  GROUPS.forEach(([title, test]) => {
    const g = rows.filter(r => !used.has(r.symbol) && test(r));
    if (!g.length) return;
    g.forEach(r => used.add(r.symbol));
    body.append(el('tr', { class: 'group' }, el('td', { colspan: 8, text: `${title} (${g.length})` })));
    g.forEach(r => {
      const btn = el('button', { class: 'sym', 'aria-expanded': String(state.open === r.symbol), text: r.symbol });
      btn.onclick = () => { state.open = state.open === r.symbol ? null : r.symbol; render(); };
      const tr = el('tr', { class: 'row' });
      tr.append(el('td', {}, btn),
        el('td', { class: 'num', text: fmt(r.close) }),
        el('td', {}, chip(r.trend_l1, false)),
        el('td', {}, chip(r.trend_l2, true)),
        el('td', {}, chip(r.pullback_today, false)),
        el('td', { class: 'num', text: r.bars_since_pullback == null ? '–' : String(r.bars_since_pullback) }),
        el('td', { class: 'num', text: r.dist_sma20_pct == null ? '–' : `${r.dist_sma20_pct > 0 ? '+' : ''}${fmt(r.dist_sma20_pct)}%` }));
      const ch = el('td');
      r.changes.forEach(c => ch.append(el('span', { class: `badge ${c.kind}`, text: c.text })));
      if (!r.changes.length) ch.append(el('span', { class: 'chip none', text: '–' }));
      tr.append(ch);
      body.append(tr);
      if (state.open === r.symbol) {
        const cell = el('td', { colspan: 8 });
        body.append(el('tr', { class: 'detail' }, cell));
        cell.append(...detail(r.symbol));
      }
    });
  });
  tbl.append(body);
}

// ---- detail: price chart with bands, arrows and a state strip --------------------------
function detail(sym) {
  const bars = (D.bars[sym] || []).slice(-D.n);
  if (!bars.length) return [el('div', { class: 'empty', text: 'No bar history stored for this symbol.' })];
  const legend = el('div', { class: 'legend' });
  [['Close', 'var(--ink)'], ['EMA 9', 'var(--ema9)'], ['SMA 20', 'var(--sma20)'], ['SMA 200', 'var(--sma200)']]
    .forEach(([t, c]) => {
      const k = el('span', { class: 'key' }); k.style.borderColor = c;
      legend.append(el('span', {}, k, t));
    });
  legend.append(el('span', { text: 'Shading: layer 1 (one tint), layer 2 on top (darker). Triangles: pullback arrows.' }));

  const W = 760, H = 330, m = { l: 30, r: 52, t: 8, b: 22 };
  const stripH = 3 * 10 + 6, plotB = H - m.b - stripH;
  const n = bars.length, bw = (W - m.l - m.r) / n;
  const X = i => m.l + bw * (i + 0.5);
  const vals = bars.flatMap(b => [b[1], b[2], b[3], b[4]]).filter(v => v != null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.05 || 1; lo -= pad; hi += pad;
  const Y = v => m.t + (plotB - m.t) * (1 - (v - lo) / (hi - lo));
  const s = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `${sym} price with moving averages` });

  // gridlines + y ticks
  for (let k = 0; k <= 4; k++) {
    const v = lo + (hi - lo) * k / 4, y = Y(v);
    s.append(svg('line', { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: 'var(--grid)', 'stroke-width': 1 }));
    const t = svg('text', { x: W - m.r + 6, y: y + 4, fill: 'var(--muted)', 'font-size': 11 });
    t.textContent = v.toFixed(2); s.append(t);
  }
  // bands: layer 1 then layer 2 (each 10% so layer 2 stacks darker, as on the chart)
  const runs = (idx) => {
    let start = null;
    const out = [];
    bars.forEach((b, i) => {
      if (b[idx]) { if (start === null) start = i; }
      else if (start !== null) { out.push([start, i - 1]); start = null; }
    });
    if (start !== null) out.push([start, n - 1]);
    return out;
  };
  [[5, 'var(--up)'], [6, 'var(--down)'], [9, 'var(--up)'], [10, 'var(--down)']].forEach(([idx, color]) =>
    runs(idx).forEach(([a, b]) => s.append(svg('rect', {
      x: m.l + bw * a, width: bw * (b - a + 1), y: m.t, height: plotB - m.t, fill: color, 'fill-opacity': 0.10 }))));

  // lines (gaps where a value is missing)
  const line = (col, color, w) => {
    let d = '', pen = false;
    bars.forEach((b, i) => {
      if (b[col] == null) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(b[col]).toFixed(1)}`; pen = true;
    });
    s.append(svg('path', { d, fill: 'none', stroke: color, 'stroke-width': w, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
  };
  line(4, 'var(--sma200)', 2); line(3, 'var(--sma20)', 2); line(2, 'var(--ema9)', 2); line(1, 'var(--ink)', 2);

  // arrows
  bars.forEach((b, i) => {
    if (!b[7] && !b[8]) return;
    const x = X(i), up = !!b[7], y = Y(b[1]) + (up ? 12 : -12);
    const pts = up ? `${x},${y - 6} ${x - 6},${y + 5} ${x + 6},${y + 5}` : `${x},${y + 6} ${x - 6},${y - 5} ${x + 6},${y - 5}`;
    s.append(svg('polygon', { points: pts, fill: up ? 'var(--up)' : 'var(--down)', stroke: 'var(--surface)', 'stroke-width': 2 }));
  });

  // x labels
  [0, Math.floor((n - 1) / 2), n - 1].forEach((i, k) => {
    const t = svg('text', { x: X(i), y: plotB + 14, 'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle',
                            fill: 'var(--muted)', 'font-size': 11 });
    t.textContent = bars[i][0]; s.append(t);
  });

  // state strip: L1, L2, arrow, one cell per bar, same x scale as the chart
  const stripTop = plotB + 22;
  [['L1', 5, 6], ['L2', 9, 10], ['PB', 7, 8]].forEach(([label, ui, di], r) => {
    const y = stripTop + r * 10;
    const t = svg('text', { x: 0, y: y + 8, fill: 'var(--muted)', 'font-size': 10 }); t.textContent = label; s.append(t);
    bars.forEach((b, i) => {
      if (!b[ui] && !b[di]) return;
      s.append(svg('rect', { x: m.l + bw * i + 0.5, y, width: Math.max(bw - 1, 1), height: 8, rx: 1,
                             fill: b[ui] ? 'var(--up)' : 'var(--down)' }));
    });
  });

  // hover layer
  const wrap = el('div', { class: 'chartwrap' });
  const tip = el('div', { class: 'tip' }); tip.hidden = true;
  const cross = svg('line', { y1: m.t, y2: plotB, stroke: 'var(--axis)', 'stroke-width': 1, visibility: 'hidden' });
  s.append(cross);
  const hit = svg('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t, fill: 'transparent' });
  s.append(hit);
  const stateText = b => (b[9] ? 'Layer 2 up' : b[10] ? 'Layer 2 down' : b[5] ? 'Layer 1 up' : b[6] ? 'Layer 1 down' : 'No trend')
                         + (b[7] ? ', arrow up' : b[8] ? ', arrow down' : '');
  const show = ev => {
    const r = s.getBoundingClientRect();
    const px = (ev.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(n - 1, Math.floor((px - m.l) / bw)));
    const b = bars[i];
    cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible');
    tip.replaceChildren(el('div', { class: 'date', text: b[0] }));
    [['Close', b[1]], ['EMA 9', b[2]], ['SMA 20', b[3]], ['SMA 200', b[4]]].forEach(([k, v]) =>
      tip.append(el('div', { class: 'r' }, el('span', { text: k }), el('b', { text: fmt(v) }))));
    tip.append(el('div', { class: 'date', text: stateText(b) }));
    tip.hidden = false;
    const left = X(i) * r.width / W;
    tip.style.left = (left > r.width / 2 ? left - tip.offsetWidth - 12 : left + 12) + 'px';
    tip.style.top = '8px';
  };
  hit.addEventListener('pointermove', show);
  hit.addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); });
  wrap.append(s, tip);

  // table view of the same data (relief for light-mode aqua, and keyboard/screen-reader access)
  const t = el('table');
  t.append(el('thead', {}, el('tr', {}, ...['Date', 'Close', 'EMA 9', 'SMA 20', 'SMA 200', 'State'].map(h =>
    el('th', { scope: 'col', text: h })))));
  const tb = el('tbody');
  bars.slice().reverse().slice(0, 60).forEach(b => tb.append(el('tr', {}, el('td', { text: b[0] }),
    ...[1, 2, 3, 4].map(k => el('td', { class: 'num', text: fmt(b[k]) })), el('td', { text: stateText(b) }))));
  t.append(tb);
  const det = el('details', {}, el('summary', { text: 'Data table (last 60 bars)' }), el('div', { class: 'scroll' }, t));
  return [legend, wrap, det];
}

// ---- header + filters --------------------------------------------------------------------
const arrows = D.rows.filter(r => r.pullback_today !== '-').length;
const l2 = D.rows.filter(r => r.trend_l2 !== '-').length;
const changed = D.rows.filter(r => r.changes.length).length;
document.getElementById('sub').textContent =
  `As of ${D.asof} · ${D.rows.length} symbols · ${arrows} arrow${arrows === 1 ? '' : 's'} today · ` +
  `${l2} in layer 2 · ${changed} changed since previous run`;
document.querySelectorAll('#trendFilter button').forEach(b => b.onclick = () => {
  state.trend = b.dataset.v;
  document.querySelectorAll('#trendFilter button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  render();
});
document.getElementById('changedOnly').onchange = e => { state.changedOnly = e.target.checked; render(); };
render();
})();
</script>
</body>
</html>
"""


def build(db_path: str, n_bars: int = 120, asof: str | None = None) -> str:
    conn = store.connect(db_path)
    try:
        rows = store.snapshot_with_changes(conn, asof)
        if not rows:
            raise SystemExit(f"No snapshots in {db_path}. Run screener.py with --db first.")
        data = {
            "asof": rows[0]["asof"], "n": n_bars, "rows": rows,
            "bars": {r["symbol"]: store.bars_for(conn, r["symbol"], n_bars) for r in rows},
        }
    finally:
        conn.close()
    # '<' is escaped so a symbol name can never close the script tag
    payload = json.dumps(data, allow_nan=False).replace("<", "\\u003c")
    return TEMPLATE.replace("__DATA__", payload)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="screener.db")
    p.add_argument("--out", default="report.html")
    p.add_argument("--bars", type=int, default=120, help="bars shown in each symbol chart")
    p.add_argument("--asof", help="report a specific stored date (default: latest)")
    a = p.parse_args()
    html = build(a.db, a.bars, a.asof)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
