## Working on issues (claude-project-kit)

- Work is tracked **only in GitHub issues**; the pinned backlog **#{{BACKLOG}}** is the priority list
  (its order *is* the priority; `Now` before `Next`). New work → new issue from the template
  (Goal / Acceptance criteria / Verification), a `P0`–`P3` label, and a line in the backlog.
- **`/next [n]`** works the next eligible issue end to end (`.claude/skills/next/SKILL.md`).
  **`/logs`** reports on unattended batch runs.
- **Never implement `needs-decision` issues**; they wait on a human decision.
- Labels: `ai-in-progress` (claimed by a session), `ai-merged` (merged into `{{INTEGRATION}}`, waiting
  for the human's push), `rework` (+ a human comment: send the result back; worked before everything
  else), `model:sonnet|opus` (model the batch runner uses), `on-hold`, `tracking` (epic).
- **Unattended:** `scripts/batch.py` runs `/next` repeatedly, one fresh session per issue
  (`--dry-run` first; stop with `touch .batch/STOP`). Usage: `docs/ai/README.md`.
- Settings of this workflow (branches, check command, triage): `.claude/workflow.json`.

## Check command

`{{CHECK}}` is what CI runs. Run it before every merge; never weaken a test to get green.

## Git rules (enforced by `.claude/hooks/guard_git.py`)

Work on `{{PREFIX}}<n>-<slug>` branches from `{{INTEGRATION}}`; merge back with `--no-ff` when the
check is green. Never commit to or merge into {{PROTECTED_LIST}}, never rebase `{{INTEGRATION}}`,
{{PUSH_RULE}} Details: `docs/GIT_WORKFLOW.md`.
