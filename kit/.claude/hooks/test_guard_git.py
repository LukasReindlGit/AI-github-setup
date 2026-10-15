#!/usr/bin/env python3
"""Self-test for guard_git.py: `python3 .claude/hooks/test_guard_git.py` (exit 1 on failure).

Runs the hook with sample PreToolUse payloads inside a throwaway git repo on a topic branch, so the
result doesn't depend on the branch you happen to be on. Extend the cases when you change the hook.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).with_name("guard_git.py")
sys.path.insert(0, str(HOOK.parent))
from guard_git import INTEGRATION, PROTECTED  # noqa: E402

P = PROTECTED[-1]  # e.g. "develop"
BLOCK, PASS = 2, 0
CASES = [
    (BLOCK, f"git push -u origin {INTEGRATION}"),
    (BLOCK, "git -C /x push"),
    (BLOCK, "cd /x && git push"),
    (BLOCK, f"git switch {P} && git merge {INTEGRATION}"),
    (BLOCK, f"(git switch {P}; git merge x)"),
    (BLOCK, f"git checkout {PROTECTED[0]}; git commit -m x"),
    (BLOCK, f"git switch {PROTECTED[0]}\ngit commit -m y"),
    (BLOCK, f"git switch {INTEGRATION} && git rebase {P}"),
    (BLOCK, "git commit --no-verify -m x"),
    (PASS, "git status"),
    (PASS, "git commit -m 'feat: x'"),
    (PASS, f"git switch {INTEGRATION} && git merge --no-ff ai/topic -m 'Merge'"),
    (PASS, f"git switch {INTEGRATION} && git merge {P}"),
    (PASS, f"git log {P}..{INTEGRATION}"),
    (PASS, f"git switch {P}"),
    (PASS, "ls"),
    (PASS, "git commit -m 'docs: explain that agents never git push'"),
    (PASS, "python3 - <<'EOF'\ns.replace('verbietet `git push`', '')\nEOF"),
    (PASS, f"gh issue comment 5 --body 'run git push -u origin {INTEGRATION}'"),
    (PASS, f"git switch -c ai/new {INTEGRATION} && git commit -m x"),
    (PASS, "git checkout -- CLAUDE.md && git commit -m x"),
]


def main():
    with tempfile.TemporaryDirectory() as repo:
        subprocess.run(["git", "init", "-q", "-b", "ai/topic", repo], check=True)
        failures = 0
        for want, cmd in CASES:
            payload = json.dumps({"cwd": repo, "tool_input": {"command": cmd}})
            got = subprocess.run(
                [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
            ).returncode
            ok = got == want
            failures += not ok
            print(f"{'ok ' if ok else 'BAD'} want={want} got={got}  {cmd!r}")
    print(f"{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
