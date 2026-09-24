#!/usr/bin/env python3
"""Block a push or a PR that the user has not approved (W2).

Wired as a PreToolUse hook on Bash. Reads the hook JSON on stdin and returns 2 when a command
would publish something, which stops the tool call and hands the reason back to the agent.

W2 is the one rule whose violation cannot be undone, so it is enforced rather than asked for.
A human pushing from their own terminal is unaffected: this only sees the agent's Bash calls.

After the user approves a specific push:  JITTER_PUSH_OK=1 git push ...

This is a reminder, not a security control. An agent that wants to get around it can, for
example by writing a script or going through ssh. It exists to catch the agent that forgets,
so when in doubt it blocks: a false positive costs one line, a missed push cannot be undone.
"""

import json
import re
import shlex
import sys

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
APPROVED = "JITTER_PUSH_OK=1"
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
    """Drop grouping words, continuations and leading VAR=value assignments."""
    approved = False
    changed = True
    while changed and tokens:
        changed = False
        while tokens and (tokens[0] in GROUPING or not tokens[0].strip()):
            tokens.pop(0)
            changed = True
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            approved = approved or tokens[0] == APPROVED
            tokens.pop(0)
            changed = True
    return tokens, approved


def publishing_in(segment, depth=0):
    """The name of the publishing command this segment runs, or None."""
    return in_tokens(words(segment), depth)


def in_tokens(tokens, depth=0):
    tokens, approved = strip_prefix(list(tokens))
    if approved or not tokens:
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
                "Once they approve, run the same command prefixed with {}.\n".format(name, APPROVED)
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
