#!/usr/bin/env python3
"""Session-start hook: say where the shared knowledge base is, and keep the clone current.

    python3 knowledge_session.py < hook-payload.json

The clone path is the first line of ~/.config/jitter-knowledge/path. On a new session it
pulls, but only a clean clone on master, fast-forward only, and it gives up quietly when
offline. Prints one line for the session. Always exits 0, so a broken setup never blocks one.
Runs on Linux and macOS with a stock python3, no dependencies.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "jitter-knowledge" / "path"
DECLINED = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "jitter-ai-agent" / "knowledge-declined"
BRANCH = "master"
SETUP = "Offer it once with the setup-extras skill, section 3."


def git(clone, *args, timeout=10):
    # Never wait on a password or a host-key prompt: nobody can answer it from a hook.
    ssh = os.environ.get("GIT_SSH_COMMAND", "ssh") + " -o BatchMode=yes -o ConnectTimeout=5"
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_SSH_COMMAND=ssh)
    return subprocess.run(
        ["git", "-C", str(clone), *args], capture_output=True, text=True, timeout=timeout, env=env, check=False,
    )


def pull(clone):
    """Return None when the clone is current, otherwise why it was not updated."""
    branch = git(clone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != BRANCH:
        return f"on branch {branch}"
    if git(clone, "status", "--porcelain").stdout.strip():
        return "uncommitted changes"
    try:
        done = git(clone, "pull", "--ff-only", "--quiet", timeout=20)
    except subprocess.TimeoutExpired:
        return "pull timed out"
    return "pull failed, offline or diverged" if done.returncode else None


def main():
    try:
        source = json.load(sys.stdin).get("source", "startup")
    except (json.JSONDecodeError, AttributeError):
        source = "startup"

    text = CONFIG.read_text(encoding="utf-8") if CONFIG.is_file() else ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        if not DECLINED.exists():
            print(f"The shared knowledge base (JitterCompany/jitter-knowledge) is not set up for this person. {SETUP}")
        return
    clone = Path(os.path.expanduser(lines[0]))
    if not (clone / "knowledge" / "index.md").is_file():
        print(f"{CONFIG} names {clone}, which holds no knowledge base clone. {SETUP}")
        return

    note = ""
    # Resume and compact continue a session that already pulled.
    if source in ("startup", "clear"):
        why = pull(clone)
        note = f" Not updated: {why}." if why else ""
    print(f"JITTER_KNOWLEDGE={clone}{note} Use the knowledge skill before guessing a part quirk, tool workaround or customer detail.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001, a hook must never break the session
        print(f"knowledge_session: {e}")
    sys.exit(0)
