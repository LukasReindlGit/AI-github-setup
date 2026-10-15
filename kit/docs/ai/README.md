# Working with Claude Code in this repo

Entry point for agents: `CLAUDE.md`. Settings of the workflow: `.claude/workflow.json`.
Installed from [claude-project-kit]({{KIT_URL}}); update it with `bootstrap.py --update` from there.

## The model in one picture

```
GitHub issue (acceptance criteria) ──► backlog #{{BACKLOG}} order ──► /next  or  scripts/batch.py
                                                              │
         {{PREFIX}}<n>-<slug> branch ◄──────────────────────────────┘
         check command + fresh-context review
                   │
         --no-ff merge into local {{INTEGRATION}}      (label: ai-merged)
                   │
   human: git push -u origin {{INTEGRATION}}  →  PR → {{BASE}}
```

The agent never pushes{{PUSH_NOTE}}. You keep control at exactly one point: the push and the PR.

## Daily use

| I want to… | Do this |
|---|---|
| Work the next issue with me watching | Fresh session: `/clear`, then `/next` |
| Work a specific issue | `/next 31` |
| Let several issues run unattended | `scripts/batch.py --dry-run`, then `scripts/run-batch.sh 3` (tmux) |
| See what the batch did / is doing | `/logs` (or `scripts/batch-report.sh`) |
| Run what CI runs | `{{CHECK}}` |
| See what's waiting for my push | `gh issue list --label ai-merged` and `git log --oneline --first-parent origin/{{INTEGRATION}}..{{INTEGRATION}}` |
| Review one issue's change | `git show <merge-commit> --first-parent` (one merge commit = one issue) |
| Hand off | `git push -u origin {{INTEGRATION}}`, open the PR to `{{BASE}}` |

**One issue per session.** `/clear` between issues; a fresh context is cheaper and better.

## Issues and labels

- New work → issue from the template, a `P0`–`P3` label, a line in **#{{BACKLOG}}**. The order there
  *is* the priority (sections: Now, Next, Later, Needs decision; batch reads only Now + Next).
- Backlog lines mentioning *approval*, *server access* or ⚠️ are never picked automatically.
- `needs-decision`: blocked on a human. Answer the questions in the issue, remove the label.
- `on-hold`: parked by you; never picked until you remove it.
- `ai-in-progress`: claimed by a session; an unfinished one is **resumed** first.
- `ai-merged`: done in `{{INTEGRATION}}`, waiting for your push.
- `rework`: add it with a comment saying what to change; worked before everything else, even when
  already `ai-merged`; the agent removes it once the rework is merged.
- `tracking`: epic; not worked directly. `scripts/batch.py --epic <n>` works an epic's checklist.
- `model:sonnet` / `model:opus`: the model the batch uses; set it to override the triage.

## Batch runs

```bash
scripts/batch.py --dry-run               # which issues, which model, why; changes nothing
scripts/run-batch.sh 3                   # dry run + 3 issues in a tmux session, logs in .batch/
scripts/batch.py --contains "login"      # only issues whose title/label contains the text
scripts/batch.py --epic 147              # only the unchecked issues of epic #147, in its order
touch .batch/STOP                        # stop after the current issue
```

Per issue a **fresh** `claude -p "/next <n> --batch <model>"` runs. Order: interrupted
`ai-in-progress`, then `rework`, then backlog order. Model: `model:*` label, else the fixed rules in
`workflow.json` → `triage`, else a cheap Haiku triage; written back as label + comment. Sonnet that
can't get the check green after three rounds escalates to Opus; Opus that fails asks on the issue
(`needs-decision`). Usage limits: the batch sleeps until the reset and resumes from the committed
branch. A crash or timeout is parked as a `wip(#n)` commit and resumed next time. Abnormal stops
open a `[auto] Batch stopped:` issue (`bug` + `P0`); off: `git config claudekit.alertIssues false`.
Logs: `.batch/runs.tsv`, `.batch/<time>-<issue>.json`.

Don't work in the checkout while a batch runs (shared working tree). Start with `--max-issues 1`.

## Guardrails

| File | What it does |
|---|---|
| `.claude/settings.json` | Allowlist for routine commands; `git push` denied |
| `.claude/hooks/guard_git.py` | Blocks push, commits/merges on protected branches, rebase/reset/force on `{{INTEGRATION}}`, `--no-verify` |
| `.claude/hooks/format_on_edit.py` | Runs the formatters from `workflow.json` after each edit |
| `.claude/skills/next/SKILL.md` | The `/next` workflow, interactive and `--batch` |

Hooks are deterministic; CLAUDE.md is advice. A rule that must always hold belongs in a hook.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Blocked by .claude/hooks/guard_git.py" | Intended; read the reason. A false positive: fix the hook and add a case to `test_guard_git.py` |
| Batch: "Unexpected git state" | A run ended off `{{INTEGRATION}}` or dirty. `git status`, check the last `.batch/*.json`, clean up, restart |
| Unattended run denied a command | Add a precise allow rule to `.claude/settings.json`; one command per Bash call; file edits via Edit/Write |
| An issue was redone although finished | It lacked `ai-merged`. Label it |
| `gh issue view` errors | Old distro `gh`; install from GitHub's apt repo |
