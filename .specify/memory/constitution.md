# Alpaca Momentum Model Constitution

> Educational Python strategy for monthly ETF momentum rotation on Alpaca paper trading.

## Version
1.0.0

---

## Context Detection for AI Agents

### 1) Interactive Mode
When the user is chatting directly (outside Ralph loop):
- Be concise and practical
- Explain strategy behavior and risks clearly
- Prefer minimal, testable changes

### 2) Ralph Loop Mode
When running via `scripts/ralph-loop.sh` or `scripts/ralph-loop-codex.sh`:
- Work autonomously on one highest-priority incomplete spec
- Implement and validate acceptance criteria
- Output `<promise>DONE</promise>` only when complete

---

## Core Principles

### I. Safety First for Trading Code
Default to paper-safe behavior, dry-run by default, and explicit execution switches.

### II. Deterministic, Auditable Logic
Keep selection and rebalance logic simple and reproducible from market data.

### III. Simplicity & YAGNI
Implement only what the active spec requires.

### IV. Minimal Surface Area
Avoid broad refactors unless they are required by acceptance criteria.

---

## Technical Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | Python 3 | Main implementation |
| Market Data | yfinance | End-of-day bars |
| Broker API | alpaca-py | Paper/live order submission |
| Config | python-dotenv | `.env` credentials |

---

## Project Structure

```
alpaca-momentum-model/
├── strategy.py
├── requirements.txt
├── scripts/
├── specs/
└── .specify/memory/constitution.md
```

---

## Ralph Wiggum Configuration

- **YOLO Mode**: DISABLED
- **Git Autonomy**: DISABLED
- **Work Item Source**: SpecKit specs in `specs/`

---

## Validation Commands

```bash
python -m py_compile strategy.py
python strategy.py --dry-run
```

---

**Created**: 2026-02-10
