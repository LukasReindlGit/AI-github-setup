#!/usr/bin/env python3
"""PostToolUse(Edit|Write): run the project's formatter on the file that was just edited.

Formatters are configured in .claude/workflow.json under "format", keyed by file extension:

    "format": {".py": "ruff format --quiet {file}", ".ts": "npx prettier --write {file}"}

`{file}` is replaced by the edited path. No entry for the extension, a missing file or a failing
formatter all end silently: this hook must never block an edit. Keep the commands to safe,
formatting-only operations. Do not put lint autofixes here (e.g. removing "unused" imports): Claude
often adds an import one edit before the code that uses it. Lint findings belong in the check
command, which runs before every merge.
"""

import json
import shlex
import subprocess
import sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
        file = data.get("tool_input", {}).get("file_path", "")
        root = Path(__file__).resolve().parent.parent.parent
        config = json.loads((root / ".claude" / "workflow.json").read_text())
        template = config.get("format", {}).get(Path(file).suffix)
        if not file or not template or not Path(file).is_file():
            return
        cmd = [part.replace("{file}", file) for part in shlex.split(template)]
        subprocess.run(cmd, cwd=root, capture_output=True, timeout=60)
    except Exception:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)
