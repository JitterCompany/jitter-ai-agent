#!/usr/bin/env python3
"""Load rules/hardware.md into a session that works on KiCad files, once per context.

    python3 hardware_rules.py --session   # SessionStart hook
    python3 hardware_rules.py --hook      # PostToolUse hook

The shell's working directory is not the project: after a `cd` into a scratch folder a
compaction would otherwise start without the hardware rules. --session looks in
$CLAUDE_PROJECT_DIR and the hook's cwd. --hook catches the rest: the first tool call that
names a .kicad_* path loads the rules if this context does not have them yet.
Always exits 0. Stock python3.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

RULES = Path(__file__).resolve().parent.parent / "rules" / "hardware.md"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "jitter-ai-agent" / "hardware-rules"


def has_kicad(folder):
    if not folder or not Path(folder).is_dir():
        return False
    top = subprocess.run(["git", "-C", folder, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=False).stdout.strip() or folder
    tracked = subprocess.run(["git", "-C", top, "ls-files", "*.kicad_pro"],
                             capture_output=True, text=True, check=False).stdout
    if tracked.strip():
        return True
    return any(next(Path(folder).glob(p), None) for p in ("*.kicad_pro", "*/*.kicad_pro", "*/*/*.kicad_pro"))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    session = payload.get("session_id") or ""
    marker = CACHE / session if session else None
    if not RULES.is_file():
        return 0

    if mode == "--session":
        folders = (os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd"), os.getcwd())
        if any(has_kicad(f) for f in folders):
            print(RULES.read_text(encoding="utf-8"))
            if marker:
                CACHE.mkdir(parents=True, exist_ok=True)
                marker.touch()
        elif marker and marker.exists():
            marker.unlink()
        return 0

    if mode == "--hook" and marker and not marker.exists():
        if ".kicad_" in json.dumps(payload.get("tool_input") or {}):
            CACHE.mkdir(parents=True, exist_ok=True)
            marker.touch()
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": payload.get("hook_event_name") or "PostToolUse",
                "additionalContext": "This session works on KiCad files. Jitter hardware rules:\n\n"
                + RULES.read_text(encoding="utf-8"),
            }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
