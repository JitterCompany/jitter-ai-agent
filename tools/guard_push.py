#!/usr/bin/env python3
"""Block a push or a PR that the user has not approved (W2).

Wired as a PreToolUse hook on Bash. Reads the hook JSON on stdin, returns 2 when the command
would publish something, which stops the tool call and hands the reason back to the agent.

W2 is the one rule in the set whose violation cannot be undone, so it is enforced rather than
asked for. The human pushing from their own terminal is unaffected: this only sees the
agent's Bash calls.

After the user approves a specific push, run it as:  JITTER_PUSH_OK=1 git push ...
"""

import json
import re
import sys

PUBLISHING = [
    (re.compile(r"\bgit\s+push\b"), "git push"),
    (re.compile(r"\bgh\s+pr\s+create\b"), "gh pr create"),
    (re.compile(r"\bgh\s+release\s+create\b"), "gh release create"),
    (re.compile(r"\bgit\s+send-email\b"), "git send-email"),
]
ESCAPE = re.compile(r"\bJITTER_PUSH_OK=1\b")
# A dry run publishes nothing.
HARMLESS = re.compile(r"--dry-run\b")
QUOTED = re.compile("'[^']*'" + r'|"[^"]*"')


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    if ESCAPE.search(command) or HARMLESS.search(command):
        return 0

    # `grep "git push" docs/` mentions a push, it does not do one.
    runnable = QUOTED.sub(" ", command)

    for pattern, name in PUBLISHING:
        if pattern.search(runnable):
            sys.stderr.write(
                "W2: `{}` needs the user's approval for this specific push, and nothing in "
                "this session shows it was given.\n"
                "Ask them, in one line, naming the branch and the remote. Committing locally "
                "is fine meanwhile.\n"
                "Once they approve, run the same command prefixed with JITTER_PUSH_OK=1.\n".format(name)
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
