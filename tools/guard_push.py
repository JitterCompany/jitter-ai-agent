#!/usr/bin/env python3
"""Block a push or a PR that the user has not approved (W2).

Wired as a PreToolUse hook on Bash. Reads the hook JSON on stdin and returns 2 when a command
would publish something, which stops the tool call and hands the reason back to the agent.

W2 is the one rule whose violation cannot be undone, so it is enforced rather than asked for.
A human pushing from their own terminal is unaffected: this only sees the agent's Bash calls.

After the user approves, the same command runs with one of:

    JITTER_PUSH_OK=1        this push only
    JITTER_PUSH_OK=session  every push in this session, once they said so
    JITTER_PUSH_OK=repo     every push in this repo for 30 days

Use the narrowest scope the user actually agreed to. A session or repo approval is remembered
in ${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/push-approvals, and deleting that file or
directory revokes it.

This is a reminder, not a security control. An agent that wants to get around it can, for
example by writing a script or going through ssh. It exists to catch the agent that forgets,
so when in doubt it blocks: a false positive costs one line, a missed push cannot be undone.
"""

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

PUBLISHING = [
    ("git", ["push"], "git push"),
    ("gh", ["pr", "create"], "gh pr create"),
    ("gh", ["release", "create"], "gh release create"),
    ("git", ["send-email"], "git send-email"),
]
# Programs that run a command line of their own, given as a string.
RUNS_A_STRING = {"bash", "sh", "zsh", "dash", "eval"}
# Programs that run the command that follows their own arguments.
WRAPPERS = {"sudo", "doas", "env", "time", "timeout", "nohup", "xargs", "setsid", "stdbuf",
            "script", "ssh-agent", "nice", "ionice"}
GROUPING = {"(", ")", "{", "}", "then", "do", "else", "elif", "!", "&&", "||", ";", "\\"}
GIT_OPTION_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
GIT_FLAG = {"--no-pager", "--paginate", "-P", "--bare", "--literal-pathspecs",
            "--no-replace-objects", "--no-optional-locks"}
HELP = {"--help", "-h"}
DRY_RUN = {"--dry-run", "-n"}
APPROVAL_VAR = "JITTER_PUSH_OK"
REPO_APPROVAL_DAYS = 30
PROGRAMS = {command for command, _, _ in PUBLISHING}

SEPARATORS = ["\n", ";", "&&", "||", "|", "&", "$(", "`"]
ARITHMETIC = re.compile(r"\$\(\([^)]*\)\)")
# A heredoc opener, not `<<<` and not a left shift.
HEREDOC = re.compile(r"(?<!<)<<-?\s*([\"']?)([A-Za-z_][A-Za-z0-9_]*)\1(?![A-Za-z0-9_])")


def quotes_balance(text):
    """Do the quotes pair up? `'fix Bob'\\''s typo'` and `"a \\" b"` say no on a naive scan."""
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        i += 1
    return quote is None


def strip_heredocs(command):
    """Drop heredoc bodies. Their text is data, not commands."""
    out = []
    terminator = None
    for line in command.splitlines():
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        out.append(line)
        found = HEREDOC.search(ARITHMETIC.sub(" ", line))
        if found:
            terminator = found.group(2)
    return "\n".join(out)


def segments(command):
    """Split into the pieces a shell would run separately, ignoring separators inside quotes."""
    text = strip_heredocs(command)
    if not quotes_balance(text):
        # Over-block rather than under-block: a missed push is the expensive direction.
        return [p.strip() for p in re.split(r"\n|;|&&|\|\||\||&|\$\(|`", text) if p.strip()]

    parts = []
    current = []
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and quote != "'" and i + 1 < len(text):
            if text[i + 1] == "\n":
                i += 2  # a line continuation joins the two lines, it does not separate them
                continue
            current.append(text[i:i + 2])
            i += 2
            continue
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            current.append(ch)
            i += 1
            continue
        hit = next((s for s in SEPARATORS if text.startswith(s, i)), None)
        if hit:
            parts.append("".join(current))
            current = []
            i += len(hit)
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def words(segment):
    """Tokenise, dropping a trailing shell comment. Quoted text stays as one token."""
    try:
        lexer = shlex.shlex(segment, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return segment.split()


def strip_prefix(tokens):
    """Drop grouping words, continuations and leading VAR=value assignments.

    Returns the remaining tokens and the approval scope the command carried, if any.
    """
    approved = None
    changed = True
    while changed and tokens:
        changed = False
        while tokens and (tokens[0] in GROUPING or not tokens[0].strip()):
            tokens.pop(0)
            changed = True
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            name, _, value = tokens[0].partition("=")
            if name == APPROVAL_VAR and value:
                approved = value
            tokens.pop(0)
            changed = True
    return tokens, approved


def publishing_in(segment, depth=0):
    """The name of the publishing command this segment runs, or None."""
    return in_tokens(words(segment), depth)


def in_tokens(tokens, depth=0):
    tokens, approved = strip_prefix(list(tokens))
    if approved:
        return None
    if not tokens:
        return None

    program = tokens[0].rsplit("/", 1)[-1]

    if depth < 3 and program in RUNS_A_STRING:
        # The command sits in an argument, as in `bash -c 'cd x && git push'`.
        for token in tokens[1:]:
            for piece in segments(token):
                found = publishing_in(piece, depth + 1)
                if found:
                    return found
        return None

    if program in WRAPPERS:
        # The real command follows the wrapper's own arguments, as in `timeout 60 git push`.
        # A stack of wrappers does not count against the nesting budget, because each hop
        # shrinks the token list, and `sudo env timeout 60 nice git push` is still one push.
        for index, token in enumerate(tokens[1:], start=1):
            previous = tokens[index - 1]
            if previous.startswith("-") and "=" not in previous:
                continue  # this token is that option's value, as in `sudo -u git`
            name = token.rsplit("/", 1)[-1]
            if name in RUNS_A_STRING or name in WRAPPERS or name in PROGRAMS:
                return in_tokens(tokens[index:], depth)
        return None

    if DRY_RUN & set(tokens) or HELP & set(tokens):
        return None

    for command, subcommand, name in PUBLISHING:
        if program != command:
            continue
        rest = tokens[1:]
        while rest and (
            rest[0] in GIT_OPTION_WITH_VALUE or rest[0] in GIT_FLAG or rest[0].startswith("--git-dir=")
        ):
            rest = rest[2:] if rest[0] in GIT_OPTION_WITH_VALUE else rest[1:]
        if rest[: len(subcommand)] == subcommand:
            return name
    return None


def state_dir():
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "jitter-ai-agent" / "push-approvals"


def repo_key(cwd):
    """A stable name for the repo the command runs in, or None outside one."""
    done = subprocess.run(
        ["git", "-C", cwd or ".", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    top = done.stdout.strip()
    if not top:
        return None
    return "repo-" + hashlib.sha1(top.encode("utf-8")).hexdigest()[:16]


def remember(scope, session_id, cwd):
    """Record a session or repo approval so the user is not asked again."""
    name = None
    if scope == "session" and session_id:
        name = "session-" + re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:64]
    elif scope == "repo":
        name = repo_key(cwd)
    if not name:
        return
    try:
        folder = state_dir()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass  # remembering is a convenience, never a reason to fail


def already_approved(session_id, cwd):
    """Did the user approve pushes for this session, or for this repo recently?"""
    folder = state_dir()
    candidates = []
    if session_id:
        candidates.append(("session-" + re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:64], None))
    key = repo_key(cwd)
    if key:
        candidates.append((key, REPO_APPROVAL_DAYS * 86400))
    for name, ttl in candidates:
        marker = folder / name
        try:
            stamp = int(marker.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if ttl is None or time.time() - stamp < ttl:
            return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    session_id = payload.get("session_id") or ""
    cwd = payload.get("cwd") or os.getcwd()

    scope = next(
        (s for s in (strip_prefix(words(seg))[1] for seg in segments(command)) if s), None
    )
    if scope in ("session", "repo"):
        remember(scope, session_id, cwd)

    for segment in segments(command):
        name = publishing_in(segment)
        if name:
            if already_approved(session_id, cwd):
                return 0
            sys.stderr.write(
                "W2: `{}` needs the user's approval for this specific push, and nothing in "
                "this session shows it was given.\n"
                "Ask them in one line, naming the branch and the remote. Committing locally "
                "is fine meanwhile.\n"
                "Once they approve, re-run it with {var}=1 for this push, {var}=session if they "
                "said yes for the rest of the session, or {var}=repo if they said yes for this "
                "repo. Use the narrowest scope they agreed to.\n".format(name, var=APPROVAL_VAR)
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
