#!/usr/bin/env python3
"""Momentum rotation strategy for Alpaca paper trading.

Rules:
- Universe: SPY, QQQ, TLT, DBC, GLD
- Monthly rebalance
- Top 3 by 6-month momentum (126 trading day return)
- 135 trading day SMA filter per selected asset
- Failed sleeves remain cash

Default mode is dry-run. Use --execute to place orders.
"""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Dict, List

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

UNIVERSE = ["SPY", "QQQ", "TLT", "DBC", "GLD"]
MOMENTUM_LOOKBACK_MONTHS = 6
SMA_WINDOW = 135
TOP_N = 3


@dataclass
class SignalRow:
    symbol: str
    close: float
    momentum_6m: float
    sma_135: float
    passes_sma: bool


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpaca momentum model")
    parser.add_argument("--execute", action="store_true", help="Submit orders (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode")
    parser.add_argument("--lookback-days", type=int, default=220, help="History days fetched for indicators")
    parser.add_argument("--as-of", type=str, default=None, help="As-of date YYYY-MM-DD for backfilled signal calc")
    return parser.parse_args()


def get_trading_client() -> TradingClient:
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY in environment")

    paper = os.getenv("PAPER", "true").strip().lower() == "true"
    return TradingClient(api_key, secret_key, paper=paper)


def required_lookback_trading_days() -> int:
    # Need one extra bar for pct_change plus enough bars for SMA.
    return max(SMA_WINDOW, 150)


def trading_days_to_calendar_days(trading_days: int, extra_calendar_buffer: int = 21) -> int:
    # Approximate 5 trading days/week + extra room for holidays and sparse data.
    return ceil((trading_days * 7) / 5) + extra_calendar_buffer


def fetch_prices(symbols: List[str], period_days: int) -> pd.DataFrame:
    # Enforce minimum warm-start history so first actionable rebalance is available.
    min_calendar_days = trading_days_to_calendar_days(required_lookback_trading_days())
    period = f"{max(period_days, min_calendar_days)}d"
    data = yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if data.empty:
        raise RuntimeError("No price data returned from yfinance")

    closes = data["Close"] if "Close" in data else data
    if isinstance(closes, pd.Series):
        closes = closes.to_frame()
    closes = closes.dropna(how="all")
    return closes




def price_on_or_before(series: pd.Series, target_date: pd.Timestamp) -> float | None:
    hist = series.loc[:target_date].dropna()
    if hist.empty:
        return None
    return float(hist.iloc[-1])


def six_calendar_month_momentum(series: pd.Series, as_of: pd.Timestamp) -> float | None:
    current = price_on_or_before(series, as_of)
    lookback_target = as_of - pd.DateOffset(months=MOMENTUM_LOOKBACK_MONTHS)
    lookback = price_on_or_before(series, lookback_target)
    if current is None or lookback is None or lookback == 0:
        return None
    return current / lookback - 1.0

def compute_signals(closes: pd.DataFrame, as_of: str | None = None) -> List[SignalRow]:
    if as_of:
        as_of_dt = pd.Timestamp(as_of)
        closes = closes.loc[:as_of_dt]

    if len(closes) < SMA_WINDOW + 1:
        raise RuntimeError("Not enough history to compute momentum and SMA")

    latest = closes.iloc[-1]
    sma = closes.rolling(SMA_WINDOW).mean().iloc[-1]

    rows: List[SignalRow] = []
    as_of_dt = closes.index[-1]
    for symbol in UNIVERSE:
        series = closes[symbol].dropna()
        m = six_calendar_month_momentum(series, as_of_dt)
        if m is None:
            continue
        c = float(latest[symbol])
        s = float(sma[symbol])
        rows.append(SignalRow(symbol=symbol, close=c, momentum_6m=float(m), sma_135=s, passes_sma=c > s))

    rows.sort(key=lambda x: x.momentum_6m, reverse=True)
    return rows


def build_target_weights(signal_rows: List[SignalRow]) -> Dict[str, float]:
    selected = signal_rows[:TOP_N]
    sleeve = 1.0 / TOP_N
    targets: Dict[str, float] = {s: 0.0 for s in UNIVERSE}

    for row in selected:
        if row.passes_sma:
            targets[row.symbol] = sleeve

    # leftover is implicit cash sleeve
    return targets


def print_signal_table(rows: List[SignalRow]) -> None:
    logging.info("Signal table (sorted by 6-calendar-month momentum):")
    for r in rows:
        logging.info(
            "%s | close=%.2f | mom6m=%+.2f%% | sma135=%.2f | pass=%s",
            r.symbol,
            r.close,
            r.momentum_6m * 100,
            r.sma_135,
            "Y" if r.passes_sma else "N",
        )


def print_targets(targets: Dict[str, float]) -> None:
    invested = sum(targets.values())
    cash = 1.0 - invested
    logging.info("Target weights:")
    for s in UNIVERSE:
        logging.info("  %s: %.2f%%", s, targets[s] * 100)
    logging.info("  CASH: %.2f%%", cash * 100)


def submit_rebalance(client: TradingClient, targets: Dict[str, float]) -> None:
    account = client.get_account()
    equity = float(account.equity)

    # Close positions not in target or target=0
    positions = client.get_all_positions()
    current_symbols = {p.symbol for p in positions}

    for pos in positions:
        symbol = pos.symbol
        target_w = targets.get(symbol, 0.0)
        if target_w == 0.0:
            qty = abs(float(pos.qty))
            side = OrderSide.SELL if float(pos.qty) > 0 else OrderSide.BUY
            logging.info("Closing %s: qty=%.6f side=%s", symbol, qty, side.value)
            order = MarketOrderRequest(symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.DAY)
            client.submit_order(order)

    # Set target notionals for positive-weight sleeves
    for symbol, weight in targets.items():
        if weight <= 0:
            continue

        target_notional = equity * weight
        logging.info("Setting %s target notional: $%.2f", symbol, target_notional)
        order = MarketOrderRequest(
            symbol=symbol,
            notional=round(target_notional, 2),
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        client.submit_order(order)

    logging.info("Rebalance orders submitted.")


def main() -> None:
    configure_logging()
    load_dotenv()
    args = parse_args()

    execute = args.execute and not args.dry_run
    mode = "EXECUTE" if execute else "DRY-RUN"
    logging.info("Starting strategy in %s mode", mode)

    min_history_days = trading_days_to_calendar_days(required_lookback_trading_days())
    effective_lookback_days = max(args.lookback_days, min_history_days)
    if effective_lookback_days > args.lookback_days:
        logging.info(
            "Extending lookback from %s to %s days to satisfy warm-start indicator history",
            args.lookback_days,
            effective_lookback_days,
        )

    closes = fetch_prices(UNIVERSE, period_days=effective_lookback_days)
    signals = compute_signals(closes, as_of=args.as_of)

    print_signal_table(signals)
    targets = build_target_weights(signals)
    print_targets(targets)

    if not execute:
        logging.info("Dry run only. No orders submitted. Use --execute to trade.")
        return

    client = get_trading_client()
    # Basic monthly guardrail message (no hard block; caller schedules monthly cadence)
    now = datetime.now().date()
    logging.info("Execution date: %s (ensure this run aligns with your monthly rebalance schedule)", now)
    submit_rebalance(client, targets)


if __name__ == "__main__":
    main()
