#!/usr/bin/env python3
"""PreToolUse(Bash) guard: enforces docs/GIT_WORKFLOW.md for agents.

Blocks (exit 2, reason goes back to Claude):
- any `git push` (the human pushes), unless allow_push is set in .claude/workflow.json
- history-changing git commands while on, or switching to, a protected branch
- rebase / reset --hard / force on the integration branch, which only grows by merges
- --no-verify

Only shell segments that actually run `git` are inspected, so text such as a commit
message or issue comment that *mentions* "git push" is not blocked.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# --- project settings: .claude/workflow.json ---
_CONFIG = json.loads((Path(__file__).resolve().parent.parent / "workflow.json").read_text())
INTEGRATION = _CONFIG["integration_branch"]  # agent integration branch: grows only by --no-ff merges
ALLOW_PUSH = bool(_CONFIG.get("allow_push", False))
# human-only branches (the base branch is always protected)
PROTECTED = tuple(dict.fromkeys([*_CONFIG.get("protected_branches", []), _CONFIG["base_branch"]]))
# ---
WRITE_VERBS = ("commit", "merge", "rebase", "reset", "cherry-pick", "revert", "am", "pull")

# Split on shell separators; strip leading subshell/keyword noise from each segment.
SEPARATORS = re.compile(r"&&|\|\||[;|\n]")
LEADING = re.compile(r"^(?:\s|\(|\$\(|\{|then\b|do\b|else\b|sudo\b|time\b)+")
# `git [-C dir] [-c k=v] <verb> <args>`
GIT = re.compile(r"^git((?:\s+-[Cc]\s+\S+)*)\s+([\w-]+)(.*)$", re.S)


def block(reason):
    print(
        f"Blocked by .claude/hooks/guard_git.py: {reason} See docs/GIT_WORKFLOW.md.",
        file=sys.stderr,
    )
    sys.exit(2)


def current_branch(cwd):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def git_calls(cmd):
    for segment in SEPARATORS.split(cmd):
        m = GIT.match(LEADING.sub("", segment))
        if m:
            yield m.group(2), m.group(3)


def main():
    data = json.load(sys.stdin)
    calls = list(git_calls(data.get("tool_input", {}).get("command", "")))
    if not calls:
        return

    # Branch at the start of the command; `git switch/checkout X` updates it for later segments.
    branch = current_branch(data.get("cwd") or ".")
    for verb, args in calls:
        if verb == "push" and not ALLOW_PUSH:
            block("agents never push (allow_push is false); leave the branch ready for the human to push.")
        if "--no-verify" in args:
            block("don't skip git hooks.")
        if verb in ("switch", "checkout"):
            # First non-flag arg is the (new) branch; `checkout -- <path>` doesn't switch.
            words = args.split()
            words = words[: words.index("--")] if "--" in words else words
            target = [w for w in words if not w.startswith("-")]
            if target:
                branch = target[0]
            continue
        if verb in WRITE_VERBS and branch in PROTECTED:
            block(f"no commits/merges on '{branch}'; use a topic branch, merge into {INTEGRATION}.")
        if branch == INTEGRATION and (
            verb == "rebase" or (verb == "reset" and "--hard" in args) or "--force" in args
        ):
            block(f"{INTEGRATION} only grows by --no-ff merges; no rebase, reset --hard, or force.")


if __name__ == "__main__":
    main()
