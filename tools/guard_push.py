#!/usr/bin/env python3
"""Block a push or a PR that the user has not approved (W2).

Wired as a PreToolUse hook on Bash. Reads the hook JSON on stdin and returns 2 when a command
would publish something, which stops the tool call and hands the reason back to the agent.

W2 is the one rule whose violation cannot be undone, so it is enforced rather than asked for.
A human pushing from their own terminal is unaffected: this only sees the agent's Bash calls.

After the user approves a specific push:  JITTER_PUSH_OK=1 git push ...

This is a reminder, not a security control. An agent that wants to get around it can, for
example by writing a script. It exists to catch the agent that forgets.
"""

import json
import re
import shlex
import sys

PUBLISHING = [
    (("git",), "push", "git push"),
    (("gh",), "pr create", "gh pr create"),
    (("gh",), "release create", "gh release create"),
    (("git",), "send-email", "git send-email"),
]
NESTING = {"bash", "sh", "zsh", "dash", "eval", "xargs", "env", "time", "nohup", "sudo", "doas"}
GIT_OPTION_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def segments(command):
    """Split a command line into the pieces a shell would run separately."""
    parts = re.split(r"\n|;|&&|\|\||\||&", strip_heredocs(command))
    return [p.strip() for p in parts if p.strip()]


def strip_heredocs(command):
    """Drop heredoc bodies. Their text is data, not commands."""
    lines = command.splitlines()
    out = []
    terminator = None
    for line in lines:
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        found = re.search(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?", line)
        out.append(line)
        if found:
            terminator = found.group(1)
    return "\n".join(out)


def words(segment):
    """Tokenise, dropping a trailing shell comment. Quoted text stays as one token."""
    try:
        lexer = shlex.shlex(segment, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return segment.split()


def publishing_in(segment, depth=0):
    """The name of the publishing command this segment runs, or None."""
    tokens = words(segment)
    if not tokens:
        return None

    approved = False
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        if tokens[0] == "JITTER_PUSH_OK=1":
            approved = True
        tokens.pop(0)
    if approved:
        return None
    if not tokens:
        return None

    if tokens[0] in NESTING and depth < 2:
        for token in tokens[1:]:
            nested = publishing_in(token, depth + 1)
            if nested:
                return nested
        return None

    if "--dry-run" in tokens:
        return None

    for program, subcommand, name in PUBLISHING:
        if tokens[0] not in program:
            continue
        rest = tokens[1:]
        while rest and (rest[0] in GIT_OPTION_WITH_VALUE or rest[0].startswith("--git-dir=")):
            rest = rest[2:] if rest[0] in GIT_OPTION_WITH_VALUE else rest[1:]
        if " ".join(rest[: len(subcommand.split())]) == subcommand:
            return name
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    for segment in segments(command):
        name = publishing_in(segment)
        if name:
            sys.stderr.write(
                "W2: `{}` needs the user's approval for this specific push, and nothing in "
                "this session shows it was given.\n"
                "Ask them in one line, naming the branch and the remote. Committing locally "
                "is fine meanwhile.\n"
                "Once they approve, run the same command prefixed with JITTER_PUSH_OK=1.\n".format(name)
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
