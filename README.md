# Alpaca Momentum Model

Educational Python implementation of a simple ETF momentum rotation strategy intended for **Alpaca paper trading**.

## Strategy Rules

- **Universe:** `SPY`, `QQQ`, `TLT`, `DBC`, `GLD`
- **Rebalance cadence:** Monthly
- **Signal 1 (Ranking):** Select top 3 assets by **6-calendar-month momentum** (month-end to month-end, prior-trading-day fallback on holidays/weekends)
- **Signal 2 (Trend filter):** For each selected asset, require price > **135 trading day SMA**
- **Cash sleeve:** If a selected asset fails the SMA filter, that sleeve remains in cash

Example:
- If all 3 selected assets pass SMA filter, target is 33.33% each
- If 2 pass, target is 33.33% + 33.33%, with 33.33% left in cash
- If none pass, portfolio is 100% cash

## Safety & Execution Model

- Default mode is **dry run** (no live/paper orders submitted)
- Use `--execute` to submit orders
- Intended for **paper** account use while validating behavior

## Disclaimer

This project is for educational purposes only and is **not investment advice**. Use at your own risk.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your Alpaca keys.

## Usage

Dry run (default):

```bash
python strategy.py
```

Explicit dry run:

```bash
python strategy.py --dry-run
```

Submit orders:

```bash
python strategy.py --execute
```

Useful options:

```bash
python strategy.py --execute --lookback-days 220 --as-of 2026-02-01
```

Warm-start behavior:
- The script now enforces a minimum indicator history window automatically.
- If `--lookback-days` is too small, it is extended so the first rebalance can use fully-formed momentum/SMA signals instead of an artificial cash-only start.

## Static PV-Style Dashboard (GitHub Pages)

Live Pages URL: https://jeeves-oc.github.io/alpaca-momentum-model/

Build the static dashboard locally:

```bash
python scripts/build_dashboard.py
```

Generated artifacts:

- `docs/index.html` (dashboard)
- `docs/metrics.csv`
- `docs/returns.csv`
- `docs/drawdowns.csv`
- `docs/metadata.json`

Backtest/report assumptions implemented:

- Warmup start: `2006-12-31`
- Simulation window: `2007-01-01` through end of the last completed month (inclusive, trading-calendar aware)
- Adjusted prices via `yfinance` with `auto_adjust=True`
- Rebalance: month-end close
- Signal: top-3 by 6-calendar-month momentum (month-end anchored)
- Trend filter: 135-trading-day SMA (`price > SMA135`)
- Sleeve-to-cash behavior when SMA fails
- Benchmarks: universe equal-weight (monthly rebalanced) + `VFINX`
- Cash + Risk-Free convention: FRED `DGS3MO` (3-Month Treasury Bill, secondary market), converted to monthly yield as `annual_yield/12` and compounded within month

## GitHub Actions monthly refresh

Workflow file: `.github/workflows/monthly-refresh.yml`

- Runs monthly and on manual dispatch
- Rebuilds static dashboard
- Deploys to GitHub Pages
- Sends Discord success notification if `DISCORD_WEBHOOK_URL` secret is configured

## Ralph Wiggum Setup (Autonomous Spec Loop)

This repo is wired for Ralph Wiggum using files from
`https://github.com/fstandhartinger/ralph-wiggum`.

### Added Ralph files

- `scripts/ralph-loop.sh`
- `scripts/ralph-loop-codex.sh`
- `scripts/rlm-subcall.sh`
- `scripts/lib/nr_of_tries.sh`
- `PROMPT_build.md`, `PROMPT_plan.md`
- `.specify/memory/constitution.md`
- `AGENTS.md`, `CLAUDE.md`
- `.cursor/commands/speckit.specify.md`, `.cursor/commands/speckit.implement.md`

### First use

1. Create specs in `specs/` (at least one `*.md` spec file).
2. Run a loop script:

```bash
./scripts/ralph-loop.sh --help
./scripts/ralph-loop-codex.sh --help
```

Then run actual loop mode when ready:

```bash
./scripts/ralph-loop.sh
# or
./scripts/ralph-loop-codex.sh
```

By constitution, YOLO mode is set to **DISABLED** in this project (`.specify/memory/constitution.md`).
