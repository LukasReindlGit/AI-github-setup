---
name: logs
description: Short read-only report of batch runs (what ran, results, what's waiting). Does nothing else.
disable-model-invocation: true
allowed-tools: Bash(scripts/batch-report.sh*)
---

# /logs: batch report

Snapshot (collected by `scripts/batch-report.sh`, read-only):

!`scripts/batch-report.sh 30`

## Your task

Turn the snapshot above into a **short report** and stop. This is strictly read-only:
**do not** run any other command, read other files, fix anything, change labels, commit, or
suggest-and-do follow-ups. If something looks wrong, *say so* in one line; the human decides.

If the snapshot above is missing (the command didn't run), run `scripts/batch-report.sh 30` once and
use its output. That is the only command you may run.

Report format (keep it under ~15 lines):

1. **Status:** batch running / finished / stopped (and why, if the log says), with time.
2. **Results:** one line per run: `#n title-ish: model, status, minutes, $cost`. Flag `blocked`,
   `escalated`, `limit`, `crash`, `max_turns` clearly.
3. **Needs you:** `needs-decision` issues, stuck `ai-in-progress` or open `rework` ones (while no
   batch is running), dirty tree / wrong branch, STOP file, open `[auto] Batch stopped:` issues.
4. **Waiting for your push:** number of unpushed merges on `{{INTEGRATION}}` and the issues they close.
   End with `git push -u origin {{INTEGRATION}}` if there are any.
