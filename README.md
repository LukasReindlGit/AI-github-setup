# claude-project-kit

A generic setup for working on GitHub projects with [Claude Code](https://claude.com/claude-code):
issue-driven, one issue per session, tests as the gate, and **the human in control at exactly one
point: the push and the PR**.

Extracted from a project that ran this way for months, with all project specifics removed.

## Use it: just give Claude the URL

In the repository you want to set up, start Claude Code and say:

> Set up this project with https://github.com/lukasreindlgit/claude-project-kit

Claude reads [`SETUP.md`](SETUP.md), asks a handful of questions (check command, base branch, push
policy, high-risk areas), runs `bootstrap.py`, adapts the project-specific parts, verifies, and
leaves the result committed on a branch for you to review and push.

By hand: `python3 bootstrap.py --target /path/to/repo --create-labels --create-backlog`, then follow
`SETUP.md` from step 3. `--dry-run` shows what would happen.

## What you get

| | |
|---|---|
| `/next [n]` | works the next backlog issue (or #n) end to end: branch → implement → check → fresh-context review → `--no-ff` merge into `ai/develop` → issue comment |
| `scripts/batch.py` | runs `/next` unattended, a fresh session per issue; picks the model per issue, waits out usage limits, resumes, escalates Sonnet → Opus, parks failures |
| `/logs` | short read-only report of batch runs |
| `guard_git.py` hook | blocks push, commits/merges on protected branches, rebase/reset/force on the integration branch, `--no-verify` |
| `format_on_edit.py` hook | runs your formatter on every edited file |
| `scripts/check.sh` | one command that mirrors CI |
| issue templates | Goal / Acceptance criteria / Verification forms (that is what makes autonomy work) |
| labels + pinned backlog | `P0`–`P3`, `needs-decision`, `ai-in-progress`, `ai-merged`, `rework`, `model:*`, … |
| `close-merged-issues.yml` | closes `ai-merged` issues once their work is on the base branch |

Everything is configured in one file in the target repo, `.claude/workflow.json`. After the setup,
`docs/ai/README.md` in that repo explains the day-to-day use.

## The idea in a picture

```
GitHub issue (acceptance criteria) ─► backlog order ─► /next  or  scripts/batch.py
                                                           │
          ai/<n>-<slug> branch ◄───────────────────────────┘
          check.sh + fresh-context review
                     │
          --no-ff merge into local ai/develop      (label: ai-merged)
                     │
   you: git push -u origin ai/develop  →  PR → main
```

## Requirements

Python 3.8+, git, [`gh`](https://cli.github.com) (logged in, a current version), Claude Code
(`claude`). `tmux` for long batch runs. Linux or macOS.

## Layout of this repo

```
SETUP.md        what Claude follows when given this repo
bootstrap.py    the installer (idempotent, --dry-run, --update)
kit/            the files that get installed, with {{TOKENS}}
tests/          tests for the installer and the guard hook
```

License: MIT.
