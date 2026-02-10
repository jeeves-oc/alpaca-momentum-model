# Alpaca Momentum Model

Educational Python implementation of a simple ETF momentum rotation strategy intended for **Alpaca paper trading**.

## Strategy Rules

- **Universe:** `SPY`, `QQQ`, `TLT`, `DBC`, `GLD`
- **Rebalance cadence:** Monthly
- **Signal 1 (Ranking):** Select top 3 assets by **6-month momentum** (approx. 126 trading days total return)
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
