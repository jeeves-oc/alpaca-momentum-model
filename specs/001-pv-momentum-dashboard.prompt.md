# Implementation Prompt Companion — Spec 001

Use this with Ralph build mode when implementing `specs/001-pv-momentum-dashboard.md`.

## Priority Guidance
1. Ensure simulation correctness first (date boundaries, rebalance timing, momentum/SMA logic).
2. Validate benchmark parity and metric formulas before polishing UI.
3. Only then finalize GitHub Pages automation and Discord notifications.

## Validation Expectations
- Add deterministic tests around rebalance dates and sleeve-to-cash outcomes.
- Add at least one fixture-driven regression check for CAGR and max drawdown.
- Confirm DBC pre-availability behavior is explicit and tested.

## Delivery Expectations
- Keep assumptions centralized in config.
- Ensure report output is reproducible from a single command.
- Ensure CI can run headlessly and publish without manual steps.
