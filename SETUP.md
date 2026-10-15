# SETUP: instructions for Claude

You were pointed at this repository to **set up the workflow in another project**. The target is
the repository you are currently working in (or the one the user named). Follow the steps in
order. Don't improvise a different design: the pieces are small and fit together.

## What you are installing

Issue-driven work with Claude Code, with the human in control at one point (push + PR):

| Principle | Mechanism |
|---|---|
| Work is defined by GitHub issues with acceptance criteria; one ordered list is the priority | Pinned backlog issue, labels, issue templates |
| The human keeps control at push + PR | Agent works on `ai/<n>-<slug>` branches, merges `--no-ff` into a local integration branch (`ai/develop`), never pushes |
| Rules that must hold are enforced, not just written down | `.claude/settings.json` deny rules + `guard_git.py` hook |
| The agent can prove its work without a human | One `scripts/check.sh` that mirrors CI |
| Small fresh context per task | One issue per session (`/next`), short CLAUDE.md |
| Unattended runs survive usage limits | `scripts/batch.py`: fresh `claude -p` per issue, model triage, resume, escalation |
| Nothing project-specific leaks into `~/.claude` | Everything lives in the target repo |

Everything is configured in `.claude/workflow.json` of the target. `bootstrap.py` does the
mechanical part; you do the project-specific part (steps 2 and 4).

## Step 0: Get the kit and the target in order

```bash
git clone --depth 1 <kit-url> "$TMPDIR/AI-github-setup"   # or use the checkout you were given
cd <target repository>                                       # must be a git repo with a GitHub origin
git status --short                                            # work on a clean tree; else tell the human
gh auth status                                                # needed for labels + backlog issue
```

If the target has uncommitted changes, stop and ask. Do the setup on a branch
(`git switch -c ai/claude-setup`), never directly on `main`/`master`/`develop`, and **never push**:
leave the push to the human unless they said otherwise.

## Step 1: Ask the human (only what you can't find out)

Look at the repo first (CI config, README, package files, branches). Ask in **one** message, with
your proposed answer for each so they can just say "yes":

1. **Check command:** what does CI run (lint, build, tests)? Proposed from CI config.
2. **Base branch:** where do the human's PRs land? (`main`? `develop`?) Proposed: the default branch.
3. **Push policy:** may the agent push? Default **no**: the human pushes `ai/develop` and opens the PR.
4. **High-risk areas** needing explicit approval (payments, auth, production data, migrations…).
   These become hard rules in CLAUDE.md and "needs approval" markers in the backlog.
5. **Backlog:** is there already a pinned backlog issue? Else it will be created.
6. **Language** for docs and issues (default: the repo's).

Everything else uses defaults. Don't ask about branch names or labels.

## Step 2: Install

```bash
python3 <kit>/bootstrap.py --target . --dry-run --create-labels --create-backlog   # look first
python3 <kit>/bootstrap.py --target . --create-labels --create-backlog \
    [--base main] [--check-cmd "npm test" ...] [--description "one line about the project"] \
    [--allow-push] [--kit-url <url you cloned from>]
```

It is idempotent and never overwrites project files (use `--update` later to refresh kit-owned
files). It: copies hooks, skills, scripts, issue templates, workflow and docs; writes
`.claude/workflow.json`; **merges** into `.claude/settings.json`; appends a managed block to
`CLAUDE.md`; adds `.batch/` to `.gitignore`; generates a first `scripts/check.sh` from what it
detected; creates the labels and the pinned backlog issue and records its number.

## Step 3: Make `scripts/check.sh` real

The generated script is a guess. Replace it with **exactly what CI runs**, so green locally means
green in CI: read `.github/workflows/*`, pin tool versions to CI's, and make it:

- runnable from a clean checkout, needing no secrets or personal `.env`;
- accepting optional test selectors in `"$@"`;
- cleaning up after itself (containers, temp DBs), exiting non-zero on any failure.

Run it. Record the baseline: if the suite is red *before* any change, write the known failures into
CLAUDE.md. A red baseline costs every future run, so say so to the human and suggest fixing it first.
In `.claude/workflow.json`, set `format` (extension → formatter command, formatting only, never lint
autofixes), `project_description` (one or two sentences, used for model triage), and `triage`
(`opus_title_regex`: strong risk words for *this* project, e.g. `migrations?|payments?|auth`).

## Step 4: CLAUDE.md and the backlog

- Complete `CLAUDE.md` above the managed block: one paragraph on what the project is and where the
  host differs from the runtime, the commands, the **hard rules** (numbered; add the high-risk areas
  from step 1), and non-obvious gotchas. For every line ask: would removing it cause mistakes?
  Keep it short (60–80 lines); long reference material goes in `docs/ai/` and is linked.
- If other agents are used (Cursor, Codex…): an `AGENTS.md` that only **points** to CLAUDE.md. Never
  duplicate rules; copies drift apart.
- Put the first issues into the backlog (`gh issue edit <n> --body-file …`): one line each, ordered:
  `- [ ] #12 Title`. Check issue quality against the templates: Goal, Acceptance criteria, and
  Verification are what makes unattended work possible.
- Don't write anything project-specific into `~/.claude/`.

## Step 5: Verify, in this order

```bash
python3 .claude/hooks/test_guard_git.py          # 21/21 passed
scripts/check.sh                                  # green, or exactly the recorded baseline
scripts/batch.py --dry-run --max-issues 5         # picks + model reasons look sane
# headless smoke test: must report status "none", no permission denials, no branch/label changes
claude -p "/next 999999 --batch sonnet" --model haiku --permission-mode auto --max-turns 15 \
  --no-session-persistence --output-format json \
  --json-schema '{"type":"object","properties":{"status":{"type":"string"},"issue":{"type":["integer","null"]},"summary":{"type":"string"}},"required":["status","issue","summary"]}'
```

After the smoke test, check `git branch` and the labels for side effects and undo them. Then a
first real run with the human watching: `scripts/batch.py --max-issues 1`.

## Step 6: Hand over

Commit the setup on its branch (`chore: set up AI-github-setup`) in logical commits. Do **not**
push or merge. Tell the human, briefly:

- what was installed and what you adapted (check command, hard rules, format, triage);
- the verification evidence (guard test count, check result, dry-run output);
- what they must do: `git push -u origin <branch>`, open the PR; optionally branch protection on
  the base branch with the CI checks as required status;
- how to use it: `docs/ai/README.md` (`/next`, `scripts/run-batch.sh`, `/logs`).

## Updating an existing installation

`workflow.json` has a `kit` entry. To update: clone the kit again and run
`python3 <kit>/bootstrap.py --target . --update`. Hooks, skills and scripts are refreshed; settings,
CLAUDE.md block and config get new keys merged; project-owned files are left alone. Review the diff.

## Pitfalls we hit (so you don't)

| Pitfall | Fix |
|---|---|
| A global `/issue`-style skill pushed and merged to `main` despite repo rules | Project skills in the repo; never rely on global workflow skills |
| Rules in several docs, enforced nowhere, partly contradictory | One source (CLAUDE.md), hooks for the hard rules, delete stale docs |
| A git guard matched "git push" inside text of a comment or commit message | `guard_git.py` inspects only shell segments that run git; keep the self-test |
| A formatter hook with lint autofix deleted freshly added imports | Format only on edit; full lint in the check command |
| Every session reinstalled the linter / improvised a test DB | A pinned, self-contained `scripts/check.sh` |
| `claude -p` in auto mode denied `gh issue edit` and chained git commands | Explicit allow rules; one command per Bash call |
| A weak model replaced a nonexistent issue number with another issue | Skill rule: an explicit number wins, else status `none`; the bogus-number smoke test |
| Triage sent everything to Opus | Rules on title/labels only, Haiku for the rest; escalation catches misses |
| `Closes #n` didn't close issues merged into a non-default branch | The `ai-merged` label + `close-merged-issues.yml` |
| Old distro `gh` broke `gh issue view` | Install `gh` from GitHub's apt repo |
| A usage limit in `-p` mode just ends the run | Commit early (the skill says so); `batch.py` waits for the reset and resumes |
