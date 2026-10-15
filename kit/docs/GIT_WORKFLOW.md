# Git workflow for agents

## Branches

- **{{PROTECTED_LIST}}:** the humans' branches. Changes land there **only through humans** (review + merge).
- **`{{INTEGRATION}}`:** the agent's integration branch. All finished agent work collects here. The
  human takes it over in one go with **one** PR `{{INTEGRATION}}` → `{{BASE}}`.
- **Topic branches:** `{{PREFIX}}<issue>-<slug>` (e.g. `{{PREFIX}}42-login-rate-limit`), always branched
  from `{{INTEGRATION}}`, one issue per branch. The number lets a later run find and resume it.
- Human feature branches: whatever the team uses.

## Hard limits for the agent

The agent must **not**:

- commit or merge **on** a protected branch, or prepare a merge into one;
- {{PUSH_BULLET}}
- rebase, reset --hard or force on `{{INTEGRATION}}`; it only grows by merges;
- skip git hooks (`--no-verify`).

Claude Code enforces this technically: `.claude/settings.json` denies `git push` (unless
`allow_push` is set) and `.claude/hooks/guard_git.py` blocks the rest. Other agents get no
technical guard; there the rule is discipline plus branch protection on the remote.

## Agent flow

1. `git status`: nothing unexpected in the way.
2. Keep `{{INTEGRATION}}` current: if it is missing, `git switch -c {{INTEGRATION}} {{BASE}}`; if the
   human has merged into `{{BASE}}` since, `git switch {{INTEGRATION}} && git merge {{BASE}}` (no rebase).
3. Topic branch: `git switch -c {{PREFIX}}<n>-<slug> {{INTEGRATION}}`.
4. Work and commit in logical units. The commit that finishes an issue says `Closes #<n>`.
5. When the check is green: `git switch {{INTEGRATION}} && git merge --no-ff {{PREFIX}}<n>-<slug>`;
   the merge message names the issue: `Merge branch '{{PREFIX}}<n>-<slug>' into {{INTEGRATION}} (#<n>)`.
6. Hand-over: tell the human the push command and list the finished issues. Unfinished work stays
   on its topic branch and is **not** merged.

## Human: taking over

1. `git push -u origin {{INTEGRATION}}`
2. Open and merge the PR `{{INTEGRATION}}` → `{{BASE}}`. The workflow `close-merged-issues.yml` closes
   the open `ai-merged` issues (except `rework`) whose merge commit is on `{{BASE}}`
   (`Closes #n` alone only fires on the repository's default branch).
3. The agent pulls `{{BASE}}` back into `{{INTEGRATION}}` on its next start.

Recommended on GitHub: branch protection / a ruleset on {{PROTECTED_LIST}} requiring your CI checks.
