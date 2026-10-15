---
name: next
description: Take the next issue from the backlog (or the given issue number) and work it end to end on a topic branch, merged into the integration branch. Never pushes.
argument-hint: "[issue-number] [--batch sonnet|opus]"
disable-model-invocation: true
---

# /next: work one backlog issue

One issue per run, then stop. The human pushes `{{INTEGRATION}}` and opens the PR; your job ends
with a clean `--no-ff` merge into the local `{{INTEGRATION}}` and a comment on the issue.
Git rules (enforced by `.claude/hooks/guard_git.py`): `docs/GIT_WORKFLOW.md`.
Project settings (branches, check command, backlog number): `.claude/workflow.json`.

Arguments: `$ARGUMENTS`
- `--batch <model>` means you were started unattended by `scripts/batch.py` on that model. Nobody
  is watching: never wait for input, follow the escalation rules in step 4, and **always** finish
  as described in step 6.

Run git and gh commands **one per Bash call**, not chained with `&&`, `||`, loops or subshells.
Single commands match the project's permission allowlist; compound ones may be denied in
unattended runs.

Create and change files **only with the Edit and Write tools**, never with scripts run through Bash
(`python - <<EOF`, `sed -i`, `perl -i`, `cat > file <<EOF`). The auto-mode classifier can deny
those, which ends an unattended run as `failed`. For a large change, make several smaller Edit
calls. Formatters are fine.

**Skip rules.** An issue is ineligible if it is closed, assigned, labelled `needs-decision`,
`on-hold`, `tracking` or `ai-merged`, or noted (in the backlog or the issue) as needing explicit
human approval (see the hard rules in CLAUDE.md) or access you don't have (servers, production).

**Rework.** A `rework` label means a human found the earlier AI result lacking and left a comment
saying what to change. Rework issues come **before** everything in the backlog, and `ai-merged`
does **not** make them ineligible (the other skip rules still apply). The task is the newest human
comment(s) after the last AI result comment, read against the original acceptance criteria; don't
redo what was already right. The rework is done when it's merged and the `rework` label is removed
(step 5).

## 1. Pick the issue

**A. The arguments contain an issue number** (always true with `--batch`):
work **exactly** that issue and never look at any other. Run
`gh issue view <n> --json number,title,body,labels,assignees,state,comments`.
- If the issue doesn't exist or is ineligible: finish with status `none` and say why. Never
  substitute a different issue.
- If it's labelled `ai-in-progress` and an unmerged branch exists
  (`git branch --no-merged {{INTEGRATION}} --list '{{PREFIX}}<n>-*'`), you're resuming interrupted
  work (usage limit, crash). Read `git log {{INTEGRATION}}..<branch>` and the comments. Branches
  already merged into `{{INTEGRATION}}` are history (e.g. the work a `rework` sent back), not resume points.

**B. No issue number** (interactive):
1. Resume first: an open issue labelled `ai-in-progress` with an unmerged `{{PREFIX}}<n>-*` branch.
2. Then rework: `gh issue list --label rework --state open`, in backlog order (unlisted ones last),
   first one that isn't ineligible.
3. Otherwise read `gh issue view {{BACKLOG}}` and walk the unchecked items in **Now**, then
   **Next**, top to bottom. Take the first one that isn't ineligible and isn't labelled
   `ai-in-progress`.
4. If nothing qualifies, report what you skipped and why, and finish with status `none`.

Claim it (if not already claimed): `gh issue edit <n> --add-label ai-in-progress`.

## 2. Prepare

```bash
git status
git switch {{INTEGRATION}}
git fetch -q origin
git merge origin/{{BASE}}                        # only if it's ahead; never rebase
git switch -c {{PREFIX}}<n>-<short-slug> {{INTEGRATION}}   # or switch to the existing unmerged {{PREFIX}}<n>-* branch
```

If `{{INTEGRATION}}` doesn't exist yet: `git switch -c {{INTEGRATION}} {{BASE}}`.
For a rework, start a fresh branch `{{PREFIX}}<n>-rework-<short-slug>` from `{{INTEGRATION}}`; the
old branch is already merged.

Uncommitted changes are only acceptable when you are resuming that same issue's branch. They are
your own interrupted work, so review them and carry on. Any other dirty state: stop with status
`failed`.

Read the issue body **and all comments**, since answers to earlier questions live there. Read
CLAUDE.md's pointers (context, file map, hand-off notes) for whatever concerns this issue.

**Blocked?** Stop when the issue is ambiguous in a way that changes behaviour, UX, data model or
security, *not* when it's just big. Then:
1. Post numbered questions with `gh issue comment <n> --body-file <file>`.
2. Swap labels: `--remove-label ai-in-progress --add-label needs-decision`. Leave `rework` on, so
   the issue comes back first once the decision is made.
3. Commit any partial work on the topic branch, **don't** merge it.
4. Finish with status `blocked`.

## 3. Implement

- Plan first when the change touches several files or the approach isn't obvious.
- Smallest change that meets every acceptance criterion; follow existing patterns.
- New logic gets tests, placed like the existing ones (see CLAUDE.md).
- Commit in logical units, early and often, because an interrupted run resumes from your commits.
  The commit that completes the issue says `Closes #<n>`.

## 4. Verify

```bash
{{CHECK}}                 # the CI mirror: lint, build, tests
```

If the check takes longer than a foreground Bash call may last (10 minutes), run it into a log
file with `run_in_background: true` and poll the log in foreground calls; piping a long run
through `tail` loses the result:

```bash
{{CHECK}} > .batch/check-<n>.log 2>&1; echo "check exit=$?" >> .batch/check-<n>.log   # run_in_background
timeout 570 bash -c 'until grep -q "^check exit=" .batch/check-<n>.log; do sleep 15; done'; tail -30 .batch/check-<n>.log
```

Every failure that doesn't also happen on `{{INTEGRATION}}` is yours to fix. When in doubt, run the
same check on `{{INTEGRATION}}` and compare. Never weaken or delete a test to get green.

**Escalation (batch mode).** If your failures are still there after three fix-and-rerun rounds:
- On **sonnet**: commit the work in progress (`wip(#<n>): …`), comment on the issue with what fails
  and what you tried, swap labels `--remove-label model:sonnet --add-label model:opus` (keep
  `ai-in-progress`), then finish with status `escalated`. An Opus run will resume from your branch.
- On **opus**: commit the work in progress, post numbered questions or findings on the issue, swap
  `ai-in-progress` for `needs-decision`, then finish with status `blocked`.

Once green, get a fresh-context review: use a subagent (model: sonnet) to review
`git diff {{INTEGRATION}}...HEAD` against the issue's acceptance criteria. Ask it for correctness
bugs and unmet criteria only, not style. Run it in the **foreground** and wait for its report
before integrating or writing your final message: a background subagent that hands back after your
final result leaves the batch runner without a structured status. Fix what's real and re-run the
check.

## 5. Integrate

```bash
git switch {{INTEGRATION}}
git merge --no-ff {{PREFIX}}<n>-<short-slug> -m "Merge branch '{{PREFIX}}<n>-<short-slug>' into {{INTEGRATION}} (#<n>)"
gh issue edit <n> --remove-label ai-in-progress --add-label ai-merged
gh issue edit <n> --remove-label rework             # rework only, and only once it's merged
```

Comment on the issue (for a rework: answer each point of the rework comment): what changed
(files/behaviour), how it was verified (check result), anything left open, and follow-ups filed as
new issues.

## 6. Finish

Before your final message, whatever the status: be on `{{INTEGRATION}}` with a clean working tree
(`git status --porcelain` empty). Unfinished work lives committed on its `{{PREFIX}}<n>-*` branch.
If a run can't get there (e.g. a denied command), the batch runner commits the leftovers as
`wip(#<n>): …` on the issue branch and the next run resumes them.

Final message, short:
- status: `merged` | `blocked` | `escalated` | `none` | `failed`
- issue, branch, merge commit
- verification evidence (test counts, lint clean)
- in interactive mode: `git push -u origin {{INTEGRATION}}`
- open questions or follow-up issues, if any
