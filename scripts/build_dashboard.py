#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

UNIVERSE = ["SPY", "QQQ", "TLT", "DBC", "GLD"]
BENCHMARKS = ["VFINX"]
WARMUP_START = "2006-12-31"
SIM_START = "2007-01-01"
SIM_END = "2026-01-31"
MOMENTUM_LOOKBACK = 126
SMA_WINDOW = 135
TOP_N = 3
CASH_ANNUAL_RETURN = 0.0
RISK_FREE_ANNUAL = 0.0
OUT_DIR = Path("docs")


@dataclass
class RebalanceDecision:
    date: pd.Timestamp
    selected: list[str]
    momentum: dict[str, float]
    sma_pass: dict[str, bool]
    weights: dict[str, float]
    cash_weight: float


def fetch_prices() -> pd.DataFrame:
    tickers = UNIVERSE + BENCHMARKS
    df = yf.download(
        tickers=tickers,
        start=WARMUP_START,
        end=(pd.Timestamp(SIM_END) + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    closes = df["Close"] if "Close" in df else df
    if isinstance(closes, pd.Series):
        closes = closes.to_frame()
    closes = closes.sort_index().dropna(how="all")
    return closes


def monthly_rebalance_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    sim_idx = index[(index >= pd.Timestamp(SIM_START)) & (index <= pd.Timestamp(SIM_END))]
    s = pd.Series(sim_idx, index=sim_idx)
    return list(s.groupby(sim_idx.to_period("M")).max().values)


def simulate(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[RebalanceDecision]]:
    prices = prices.copy()
    universe_px = prices[UNIVERSE]

    returns = universe_px.pct_change().fillna(0.0)
    idx = universe_px.index
    rebalance_dates = set(monthly_rebalance_dates(idx))

    weights = pd.DataFrame(0.0, index=idx, columns=UNIVERSE)
    decisions: list[RebalanceDecision] = []

    current_weights = {t: 0.0 for t in UNIVERSE}

    for dt in idx:
        if dt in rebalance_dates and pd.Timestamp(SIM_START) <= dt <= pd.Timestamp(SIM_END):
            momentum_scores = {}
            sma_pass = {}
            eligible = []

            for t in UNIVERSE:
                series = universe_px[t].loc[:dt].dropna()
                if len(series) < max(MOMENTUM_LOOKBACK + 1, SMA_WINDOW):
                    continue
                mom = series.iloc[-1] / series.iloc[-(MOMENTUM_LOOKBACK + 1)] - 1
                sma = series.iloc[-SMA_WINDOW:].mean()
                momentum_scores[t] = float(mom)
                sma_pass[t] = bool(series.iloc[-1] > sma)
                eligible.append(t)

            ranked = sorted(eligible, key=lambda t: momentum_scores[t], reverse=True)
            selected = ranked[:TOP_N]
            sleeve = 1.0 / TOP_N

            current_weights = {t: 0.0 for t in UNIVERSE}
            for t in selected:
                if sma_pass[t]:
                    current_weights[t] = sleeve

            cash_weight = 1.0 - sum(current_weights.values())
            decisions.append(
                RebalanceDecision(
                    date=dt,
                    selected=selected,
                    momentum={k: momentum_scores.get(k, np.nan) for k in UNIVERSE},
                    sma_pass={k: sma_pass.get(k, False) for k in UNIVERSE},
                    weights=current_weights.copy(),
                    cash_weight=float(cash_weight),
                )
            )

        weights.loc[dt] = pd.Series(current_weights)

    sim_mask = (idx >= pd.Timestamp(SIM_START)) & (idx <= pd.Timestamp(SIM_END))
    sim_idx = idx[sim_mask]
    weights = weights.loc[sim_idx]
    returns = returns.loc[sim_idx]

    cash_daily = (1 + CASH_ANNUAL_RETURN) ** (1 / 252.0) - 1
    invested = (weights * returns).sum(axis=1)
    cash_component = (1.0 - weights.sum(axis=1)) * cash_daily
    strategy_ret = invested + cash_component

    # Equal-weight benchmark: monthly rebalanced equal-weight across available universe members
    eq_weights = pd.DataFrame(0.0, index=sim_idx, columns=UNIVERSE)
    cur_eq = {t: 0.0 for t in UNIVERSE}
    rebalance_dates_sim = set(monthly_rebalance_dates(sim_idx))
    for dt in sim_idx:
        if dt in rebalance_dates_sim:
            available = [t for t in UNIVERSE if pd.notna(universe_px.loc[dt, t])]
            if available:
                w = 1.0 / len(available)
                cur_eq = {t: (w if t in available else 0.0) for t in UNIVERSE}
            else:
                cur_eq = {t: 0.0 for t in UNIVERSE}
        eq_weights.loc[dt] = pd.Series(cur_eq)

    eq_ret = (eq_weights * returns.loc[sim_idx]).sum(axis=1)

    vfinx_px = prices["VFINX"].loc[sim_idx].ffill()
    vfinx_ret = vfinx_px.pct_change().fillna(0.0)

    rets = pd.DataFrame({
        "Strategy": strategy_ret,
        "EqualWeight": eq_ret,
        "VFINX": vfinx_ret,
    }, index=sim_idx)

    equity = (1 + rets).cumprod()
    drawdown = equity / equity.cummax() - 1

    return rets, drawdown, decisions


def annualized_return(r: pd.Series) -> float:
    n = len(r)
    if n == 0:
        return np.nan
    total = (1 + r).prod()
    return total ** (252 / n) - 1


def annualized_vol(r: pd.Series) -> float:
    return r.std(ddof=0) * np.sqrt(252)


def sharpe(r: pd.Series, rf_annual: float = 0.0) -> float:
    rf_daily = (1 + rf_annual) ** (1 / 252.0) - 1
    ex = r - rf_daily
    denom = ex.std(ddof=0)
    return np.nan if denom == 0 else ex.mean() / denom * np.sqrt(252)


def sortino(r: pd.Series, rf_annual: float = 0.0) -> float:
    rf_daily = (1 + rf_annual) ** (1 / 252.0) - 1
    ex = r - rf_daily
    downside = ex[ex < 0]
    if len(downside) == 0:
        return np.nan
    dd = np.sqrt((downside**2).mean())
    return np.nan if dd == 0 else ex.mean() / dd * np.sqrt(252)


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1
    return dd.min()


def calmar(r: pd.Series) -> float:
    mdd = abs(max_drawdown(r))
    cagr = annualized_return(r)
    return np.nan if mdd == 0 else cagr / mdd


def yearly_returns(r: pd.Series) -> pd.Series:
    return (1 + r).groupby(r.index.year).prod() - 1


def metrics_table(rets: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for c in rets.columns:
        r = rets[c]
        y = yearly_returns(r)
        rows[c] = {
            "CAGR": annualized_return(r),
            "Volatility": annualized_vol(r),
            "Sharpe": sharpe(r, RISK_FREE_ANNUAL),
            "Sortino": sortino(r, RISK_FREE_ANNUAL),
            "Calmar": calmar(r),
            "MaxDrawdown": max_drawdown(r),
            "BestYear": y.max() if len(y) else np.nan,
            "WorstYear": y.min() if len(y) else np.nan,
            "WinRate": float((r > 0).mean()),
        }
    return pd.DataFrame(rows).T


def monthly_table(r: pd.Series) -> pd.DataFrame:
    m = (1 + r).resample("ME").prod() - 1
    df = pd.DataFrame({"ret": m})
    df["Year"] = df.index.year
    df["Month"] = df.index.month
    p = df.pivot(index="Year", columns="Month", values="ret").sort_index()
    return p


def to_pct(x: float) -> str:
    if pd.isna(x):
        return "—"
    return f"{x*100:.2f}%"


def to_num(x: float) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:.2f}"


def html_table(df: pd.DataFrame, percent_cols: set[str] | None = None, precision: int = 2) -> str:
    percent_cols = percent_cols or set()
    headers = "".join(f"<th>{c}</th>" for c in [df.index.name or ""] + list(df.columns))
    body_rows = []
    for idx, row in df.iterrows():
        tds = [f"<td><strong>{idx}</strong></td>"]
        for c in df.columns:
            v = row[c]
            if c in percent_cols:
                tds.append(f"<td>{to_pct(v)}</td>")
            else:
                if isinstance(v, (float, np.floating)):
                    tds.append(f"<td>{v:.{precision}f}</td>")
                else:
                    tds.append(f"<td>{v}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def generate_html(rets: pd.DataFrame, drawdown: pd.DataFrame, metrics: pd.DataFrame, decisions: list[RebalanceDecision]) -> str:
    equity = (1 + rets).cumprod()

    metrics_disp = metrics.copy()
    for c in ["CAGR", "Volatility", "MaxDrawdown", "BestYear", "WorstYear", "WinRate"]:
        metrics_disp[c] = metrics_disp[c].map(to_pct)
    for c in ["Sharpe", "Sortino", "Calmar"]:
        metrics_disp[c] = metrics_disp[c].map(to_num)

    yearly = ((1 + rets).groupby(rets.index.year).prod() - 1).copy()
    yearly.index.name = "Year"

    month = monthly_table(rets["Strategy"])
    month.index.name = "Year"
    month.columns = [datetime(2000, m, 1).strftime("%b") for m in month.columns]

    holdings_rows = []
    for d in decisions:
        row = {"Date": d.date.strftime("%Y-%m-%d")}
        row.update({k: d.weights.get(k, 0.0) for k in UNIVERSE})
        row["CASH"] = d.cash_weight
        holdings_rows.append(row)
    holdings = pd.DataFrame(holdings_rows).set_index("Date") if holdings_rows else pd.DataFrame()

    log_rows = []
    for d in decisions:
        rec = {
            "Date": d.date.strftime("%Y-%m-%d"),
            "Top1": d.selected[0] if len(d.selected) > 0 else "",
            "Top2": d.selected[1] if len(d.selected) > 1 else "",
            "Top3": d.selected[2] if len(d.selected) > 2 else "",
            "CashSleeves": int(round(d.cash_weight * 3)),
        }
        for t in UNIVERSE:
            rec[f"Mom_{t}"] = d.momentum.get(t, np.nan)
            rec[f"SMApass_{t}"] = "Y" if d.sma_pass.get(t, False) else "N"
        log_rows.append(rec)
    log_df = pd.DataFrame(log_rows).set_index("Date") if log_rows else pd.DataFrame()

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo("America/New_York"))

    chart_data = {
        "dates": [d.strftime("%Y-%m-%d") for d in equity.index],
        "equity": {c: [float(x) for x in equity[c].values] for c in equity.columns},
        "drawdown": {c: [float(x) for x in drawdown[c].values] for c in drawdown.columns},
    }

    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>PV-Style Momentum Dashboard</title>
<script src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></script>
<style>
:root {{--bg:#0b1220;--card:#121b2b;--text:#e7eef9;--muted:#9fb0c9;--accent:#68b3ff;--good:#21c87a;--bad:#ff6f6f;}}
:root.light {{--bg:#f5f7fb;--card:#ffffff;--text:#0d1b2a;--muted:#47607a;--accent:#0b66d6;--good:#0f9d58;--bad:#d93025;}}
body{{font-family:Inter,system-ui,Arial,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:16px;}}
.wrap{{max-width:1200px;margin:0 auto;}}
.banner{{background:linear-gradient(90deg,var(--accent),#7d6bff);color:white;padding:10px 14px;border-radius:12px;margin-bottom:14px;font-weight:600;}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;}}
button{{background:var(--card);color:var(--text);border:1px solid #3a4d6b;padding:8px 12px;border-radius:10px;cursor:pointer;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:12px 0;}}
.card{{background:var(--card);border-radius:12px;padding:12px;}}
.k{{font-size:12px;color:var(--muted);}}
.v{{font-size:24px;font-weight:800;}}
section{{margin:14px 0;}}
table{{width:100%;border-collapse:collapse;font-size:12px;display:block;overflow:auto;}}
th,td{{padding:6px 8px;border-bottom:1px solid #2a3a52;text-align:right;white-space:nowrap;}}
th:first-child,td:first-child{{text-align:left;position:sticky;left:0;background:var(--card);}}
small{{color:var(--muted);}}
</style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"top\">
    <h1>PV-Style Momentum Dashboard</h1>
    <button onclick=\"toggleTheme()\">Toggle Dark/Light</button>
  </div>
  <div class=\"banner\">✅ Monthly refresh complete. Simulation window: {SIM_START} → {SIM_END}. Updated UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} | Local (America/New_York): {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}</div>

  <section class=\"grid\">
    <div class=\"card\"><div class=\"k\">Strategy CAGR</div><div class=\"v\">{to_pct(metrics.loc['Strategy','CAGR'])}</div></div>
    <div class=\"card\"><div class=\"k\">Strategy Max Drawdown</div><div class=\"v\">{to_pct(metrics.loc['Strategy','MaxDrawdown'])}</div></div>
    <div class=\"card\"><div class=\"k\">Strategy Sharpe</div><div class=\"v\">{to_num(metrics.loc['Strategy','Sharpe'])}</div></div>
    <div class=\"card\"><div class=\"k\">Strategy Sortino</div><div class=\"v\">{to_num(metrics.loc['Strategy','Sortino'])}</div></div>
  </section>

  <section class=\"card\"><h3>Performance Summary</h3>{html_table(metrics_disp)}</section>

  <section class=\"card\"><h3>Equity Curve</h3><div id=\"equity\" style=\"height:420px\"></div></section>
  <section class=\"card\"><h3>Drawdown Curve</h3><div id=\"dd\" style=\"height:340px\"></div></section>

  <section class=\"card\"><h3>Calendar Year Returns</h3>{html_table(yearly, percent_cols=set(yearly.columns))}</section>
  <section class=\"card\"><h3>Monthly Returns (Strategy)</h3>{html_table(month, percent_cols=set(month.columns))}</section>
  <section class=\"card\"><h3>Holdings / Weights Timeline (Monthly Rebalance)</h3>{html_table(holdings, percent_cols=set(holdings.columns)) if not holdings.empty else '<p>No holdings records.</p>'}</section>
  <section class=\"card\"><h3>Rebalance Log (Top-3, SMA filter, cash sleeves)</h3>{html_table(log_df, percent_cols={c for c in log_df.columns if c.startswith('Mom_')}) if not log_df.empty else '<p>No rebalance records.</p>'}</section>

  <section class=\"card\">
    <h3>Methodology / Metadata</h3>
    <small>
      Data source: Yahoo Finance via yfinance (auto_adjust=True).<br>
      Universe: {', '.join(UNIVERSE)}. Benchmark: VFINX + equal-weight monthly rebalanced universe.<br>
      Warmup starts at {WARMUP_START}; simulation window is {SIM_START} through {SIM_END} inclusive (trading-calendar aware).<br>
      Rebalance: month-end close; rank by 126-trading-day momentum; select top 3; 135-trading-day SMA filter per sleeve; failed sleeve in cash.<br>
      DBC availability policy: excluded from ranking until historical data exists on date (no synthetic pre-inception).<br>
      Cash annual return assumption: {CASH_ANNUAL_RETURN:.2%}; risk-free for Sharpe/Sortino: {RISK_FREE_ANNUAL:.2%}.
    </small>
  </section>
</div>
<script>
const data = {json.dumps(chart_data)};
function traces(kind){{
  return Object.keys(data[kind]).map(k => ({{x:data.dates,y:data[kind][k],name:k,type:'scatter',mode:'lines'}}));
}}
Plotly.newPlot('equity', traces('equity'), {{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{{color:getComputedStyle(document.body).getPropertyValue('--text')}}}});
Plotly.newPlot('dd', traces('drawdown'), {{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{{color:getComputedStyle(document.body).getPropertyValue('--text')}},yaxis:{{tickformat:'.0%'}}}});
function toggleTheme(){{
  document.documentElement.classList.toggle('light');
  localStorage.setItem('theme', document.documentElement.classList.contains('light')?'light':'dark');
}}
(function(){{ if(localStorage.getItem('theme')==='light') document.documentElement.classList.add('light'); }})();
</script>
</body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = fetch_prices()
    rets, drawdown, decisions = simulate(prices)
    metrics = metrics_table(rets)

    html = generate_html(rets, drawdown, metrics, decisions)
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")

    metrics.to_csv(OUT_DIR / "metrics.csv")
    rets.to_csv(OUT_DIR / "returns.csv")
    drawdown.to_csv(OUT_DIR / "drawdowns.csv")

    meta = {
        "warmup_start": WARMUP_START,
        "sim_start": SIM_START,
        "sim_end": SIM_END,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe": UNIVERSE,
        "benchmarks": ["EqualWeight", "VFINX"],
        "momentum_lookback_days": MOMENTUM_LOOKBACK,
        "sma_window_days": SMA_WINDOW,
        "top_n": TOP_N,
        "cash_annual_return": CASH_ANNUAL_RETURN,
    }
    (OUT_DIR / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Built dashboard to {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
