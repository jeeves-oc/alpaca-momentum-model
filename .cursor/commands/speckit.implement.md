---
description: Execute implementation using Ralph Wiggum iterative loops on specs
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This command launches the Ralph Wiggum implementation loop to process specifications autonomously. The agent iterates until acceptance criteria and Completion Signal requirements pass.

## Prerequisites

1. **Ralph Wiggum Plugin**: Must be installed in Claude Code
   ```
   /plugin install ralph-loop@claude-plugins-official
   ```

2. **At least one spec**: Specs must exist in `specs/` with Completion Signal sections

3. **Context files**:
   - `.specify/memory/constitution.md` — Project principles
   - `AGENTS.md` — Development guidelines
   - `RALPH_PROMPT.md` — Master prompt (optional, can use inline)

## Execution

### Option A: Single Spec

If `$ARGUMENTS` specifies a single spec (e.g., "001-user-auth"):

```
/ralph-loop:ralph-loop "Implement the spec $ARGUMENTS from specs/$ARGUMENTS/spec.md.

Context:
- Read .specify/memory/constitution.md for project principles
- Read AGENTS.md for development guidelines

Process:
1. Read and understand the full spec
2. Implement all requirements
3. Complete ALL items in the Completion Signal section
4. Run all tests (unit, integration, browser, visual)
5. Verify no console/network errors
6. Commit and push changes
7. Deploy if required and verify
8. Iterate until all checks pass

Output <promise>DONE</promise> when ALL checks pass." --completion-promise "DONE" --max-iterations 30
```

### Option B: All Specs (Master Loop)

If no specific spec provided, run the master loop:

```
/ralph-loop:ralph-loop "Work through all specifications in specs/ folder, implementing each one until its acceptance criteria pass, then move to the next.

Context:
- Read .specify/memory/constitution.md for project principles
- Read AGENTS.md for development guidelines

For each spec in numerical order:
1. Read the spec from specs/{spec-name}/spec.md
2. Implement all requirements
3. Complete ALL items in the Completion Signal section
4. Commit, push, and verify deployment
5. Update history if required
6. Move to next spec

Output <promise>ALL_DONE</promise> when all specs complete." --completion-promise "ALL_DONE" --max-iterations 100
```

## Fallback (No Ralph Plugin)

If the Ralph Wiggum plugin is not available:

1. Read `RALPH_PROMPT.md` for the master prompt
2. Manually iterate through specs in order
3. For each spec, implement until Completion Signal requirements are met
4. Commit and push after each major milestone
5. Continue until all specs complete
