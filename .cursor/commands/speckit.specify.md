---
description: Create or update a feature specification from a natural language description.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

The text after `/speckit.specify` is the feature description. Do not ask the user to repeat it unless it is empty.

Given that description, do this:

1. **Generate a concise short name** (2-4 words) for the spec folder:
   - Extract the most meaningful keywords
   - Use action-noun format when possible (e.g., "user-auth", "billing-dashboard")
   - Preserve technical terms and acronyms (OAuth2, JWT, API)

2. **Determine the next spec number** (NO BRANCH CREATION):

   a. List existing spec directories:
      ```bash
      ls -d specs/[0-9]*/ 2>/dev/null | sort -t/ -k2 -n
      ```

   b. Find the highest number N and use N+1 (zero-padded to 3 digits)

   c. Create the spec directory structure:
      ```bash
      mkdir -p specs/NNN-short-name/checklists
      ```

   d. Set SPEC_FILE = `specs/NNN-short-name/spec.md`

3. Load `templates/spec-template.md` to understand required sections.

4. Write the spec using the template structure, replacing placeholders with concrete details derived from the feature description while preserving section order and headings.

5. **Completion Signal**: Ensure the spec includes a `## Completion Signal` section with:
   - Implementation checklist
   - Testing requirements
   - Iteration instructions
   - Completion promise (`<promise>DONE</promise>`)

6. **Create a quality checklist** at `specs/NNN-short-name/checklists/requirements.md` using `templates/checklist-template.md`.

7. If anything is ambiguous, add up to 3 `[NEEDS CLARIFICATION: ...]` markers in the spec. For each marker, present a clear question and suggested answers.

## Output

Return: SUCCESS (spec ready for implementation via Ralph Wiggum)
