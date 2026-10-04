#!/usr/bin/env python3
"""Ask the user before the agent publishes something that is hard to take back (W2).

Wired as a PreToolUse hook on Bash. Reads the hook JSON on stdin. When a command would
publish something that needs approval, it answers with permissionDecision "ask", so Claude
Code shows the user its own approval prompt. Everything else passes untouched.

Needs approval:
    git push to master or main, also through HEAD or the branch's upstream
    git push --force, a +refspec, --delete, a :refspec, --mirror, --all, --tags, a tag
    git push through xargs, or from a detached HEAD, where the target cannot be read
    gh pr create, gh pr merge, gh release create, git send-email
Free:
    git push of a feature branch, which a PR review covers before it reaches master

A human pushing from their own terminal is unaffected: this only sees the agent's Bash calls.

This is a reminder, not a security control. An agent that wants to get around it can, for
example by writing a script or going through ssh. It exists to catch the agent that forgets,
so when in doubt it asks: a false positive costs one click, a missed push cannot be undone.
"""

import json
import os
import re
import shlex
import subprocess
import sys

PUBLISHING = [
    ("git", ["push"], "git push"),
    ("gh", ["pr", "create"], "gh pr create"),
    ("gh", ["pr", "merge"], "gh pr merge"),
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
PROTECTED = {"master", "main"}
# Push options that publish more than one branch, or rewrite or remove what is there.
PUSH_ASKS = {
    "-f": "a force push", "--force": "a force push", "--force-with-lease": "a force push",
    "--force-if-includes": "a force push", "-d": "a branch delete", "--delete": "a branch delete",
    "--mirror": "a mirror push", "--all": "a push of every branch", "--tags": "a push of every tag",
    "--follow-tags": "a push with tags",
}
PUSH_OPTION_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
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
    changed = True
    while changed and tokens:
        changed = False
        while tokens and (tokens[0] in GROUPING or not tokens[0].strip()):
            tokens.pop(0)
            changed = True
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens.pop(0)
            changed = True
    return tokens


def publishing_in(segment, cwd, depth=0):
    """Why this segment needs approval, or None."""
    return in_tokens(words(segment), cwd, depth)


def in_tokens(tokens, cwd, depth=0, via_xargs=False):
    tokens = strip_prefix(list(tokens))
    if not tokens:
        return None

    program = tokens[0].rsplit("/", 1)[-1]

    if depth < 3 and program in RUNS_A_STRING:
        # The command sits in an argument, as in `bash -c 'cd x && git push'`.
        for token in tokens[1:]:
            for piece in segments(token):
                found = publishing_in(piece, cwd, depth + 1)
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
                return in_tokens(tokens[index:], cwd, depth, via_xargs or program == "xargs")
        return None

    if DRY_RUN & set(tokens) or HELP & set(tokens):
        return None

    for command, subcommand, name in PUBLISHING:
        if program != command:
            continue
        rest = tokens[1:]
        repo = cwd
        while rest and (
            rest[0] in GIT_OPTION_WITH_VALUE or rest[0] in GIT_FLAG or rest[0].startswith("--git-dir=")
        ):
            if rest[0] == "-C" and len(rest) > 1:
                repo = os.path.join(repo, os.path.expanduser(rest[1]))
            rest = rest[2:] if rest[0] in GIT_OPTION_WITH_VALUE else rest[1:]
        if rest[: len(subcommand)] != subcommand:
            continue
        if name != "git push":
            return name
        if via_xargs:
            return "git push with a target xargs fills in"
        return push_needs_approval(rest[1:], repo)
    return None


def git_out(repo, *args):
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def push_needs_approval(args, repo):
    """Why this `git push <args>` needs approval, or None for a feature branch."""
    positional = []
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in PUSH_ASKS:
            return "git push, " + PUSH_ASKS[arg]
        elif arg.split("=", 1)[0] in PUSH_ASKS:
            return "git push, " + PUSH_ASKS[arg.split("=", 1)[0]]
        elif arg in PUSH_OPTION_WITH_VALUE:
            skip = True
        elif not arg.startswith("-"):
            positional.append(arg)

    current = git_out(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    refspecs = positional[1:]
    if not refspecs:
        # The target is the current branch's upstream, or the branch of the same name.
        if current is None:
            return "git push from a detached HEAD or outside a repo"
        upstream = git_out(repo, "rev-parse", "--abbrev-ref", current + "@{upstream}")
        targets = [current] + ([upstream.split("/", 1)[-1]] if upstream else [])
        hit = next((b for b in targets if b in PROTECTED), None)
        return f"git push to {hit}" if hit else None

    for spec in refspecs:
        if spec.startswith("+"):
            return "git push, a force push"
        src, _, dst = spec.partition(":")
        if not src:
            return "git push, a branch delete"
        target = dst or src
        if target == "HEAD" or target == "@":
            if current is None:
                return "git push from a detached HEAD"
            target = current
        if target.startswith("refs/tags/") or git_out(repo, "show-ref", "--verify", "--quiet", "refs/tags/" + target) is not None:
            return f"git push of tag {target}"
        target = target.removeprefix("refs/heads/")
        if target in PROTECTED:
            return f"git push to {target}"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.getcwd()

    for segment in segments(command):
        reason = publishing_in(segment, cwd)
        if reason:
            json.dump({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"W2: {reason} needs your approval.",
            }}, sys.stdout)
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
