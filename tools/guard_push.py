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

The branch is read in the session's folder, or in the folder a `cd` or `pushd` earlier in
the same command moved to. A `cd` it cannot follow makes a later push ask. A push from a
worktree that a `git worktree add` earlier in the same command creates uses the branch
that worktree will have, since the folder does not exist yet when the guard runs.

Opt-out per machine: JITTER_PUBLISH_ALLOW holds a comma-separated list of the names in
PUBLISHING other than "git push", for example "gh pr create". Set it in the "env" block of
~/.claude/settings.json. A push to master, a force push or a tag cannot be opted out.

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
CHANGES_DIR = {"cd", "pushd", "popd"}
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
ALLOW_VAR = "JITTER_PUBLISH_ALLOW"
OPTIONAL = {name for _, _, name in PUBLISHING if name != "git push"}

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


def publishing_in(segment, cwd, planned=None, depth=0):
    """Why this segment needs approval, or None."""
    return in_tokens(words(segment), cwd, planned or {}, depth)


def git_options(rest, repo):
    """Skip git's own options. Returns the folder `-C` points at and what follows."""
    while rest and (
        rest[0] in GIT_OPTION_WITH_VALUE or rest[0] in GIT_FLAG or rest[0].startswith("--git-dir=")
    ):
        if rest[0] == "-C" and len(rest) > 1:
            path = os.path.expanduser(rest[1])
            repo = path if os.path.isabs(path) else repo and os.path.join(repo, path)
        rest = rest[2:] if rest[0] in GIT_OPTION_WITH_VALUE else rest[1:]
    return repo, rest


WORKTREE_ADD_VALUE = {"-b", "-B", "--reason"}


def planned_worktree(segment, cwd):
    """For `git worktree add`: (folder, what it will hold), else None.

    What it holds is {"repo", "branch", "upstream"}, with the branch None when it will be
    detached. The branch follows git's own choice: -b/-B, else an existing local branch,
    else a remote branch of that name (git creates a tracking branch), else a new branch
    named after the folder when no commit is given, else detached.
    """
    tokens = strip_prefix(words(segment))
    if not tokens or tokens[0].rsplit("/", 1)[-1] != "git":
        return None
    repo, rest = git_options(tokens[1:], cwd)
    if rest[:2] != ["worktree", "add"] or repo is None:
        return None
    branch, detach, no_track, positional = None, False, False, []
    args = iter(rest[2:])
    for arg in args:
        if arg in ("-b", "-B"):
            branch = next(args, None)
        elif arg in WORKTREE_ADD_VALUE:
            next(args, None)
        elif arg in ("--detach", "-d"):
            detach = True
        elif arg == "--no-track":
            no_track = True
        elif not arg.startswith("-"):
            positional.append(arg)
    if not positional:
        return None
    folder = os.path.normpath(os.path.join(repo, os.path.expanduser(positional[0])))
    start = positional[1] if len(positional) > 1 else None
    upstream = None
    if detach:
        branch = None
    elif branch is None and start is None:
        branch = os.path.basename(folder)
    elif branch is None:
        remote = git_out(repo, "for-each-ref", "--format=%(refname:lstrip=3)",
                         "refs/remotes/*/" + start)
        if git_out(repo, "show-ref", "--verify", "--quiet", "refs/heads/" + start) is not None:
            branch = start
            upstream = git_out(repo, "rev-parse", "--abbrev-ref", start + "@{upstream}")
            upstream = upstream and upstream.split("/", 1)[-1]
        elif remote:
            branch, upstream = start, start
    if branch and start and not no_track and upstream is None:
        # A start point on a remote branch makes it the upstream, as in `-b x origin/master`.
        if git_out(repo, "rev-parse", "--verify", "--quiet", "refs/remotes/" + start) is not None:
            upstream = start.split("/", 1)[-1]
    return folder, {"repo": repo, "branch": branch, "upstream": upstream}


def in_tokens(tokens, cwd, planned, depth=0, via_xargs=False):
    tokens = strip_prefix(list(tokens))
    if not tokens:
        return None

    program = tokens[0].rsplit("/", 1)[-1]

    if depth < 3 and program in RUNS_A_STRING:
        # The command sits in an argument, as in `bash -c 'cd x && git push'`.
        for token in tokens[1:]:
            for piece in segments(token):
                found = publishing_in(piece, cwd, planned, depth + 1)
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
                return in_tokens(tokens[index:], cwd, planned, depth, via_xargs or program == "xargs")
        return None

    if DRY_RUN & set(tokens) or HELP & set(tokens):
        return None

    for command, subcommand, name in PUBLISHING:
        if program != command:
            continue
        repo, rest = git_options(tokens[1:], cwd)
        if rest[: len(subcommand)] != subcommand:
            continue
        if name != "git push":
            return name
        if via_xargs:
            return "git push with a target xargs fills in"
        return push_needs_approval(rest[1:], repo, planned)
    return None


def git_out(repo, *args):
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def push_needs_approval(args, repo, planned=None):
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

    if repo is None:
        return "git push after a cd the guard cannot follow (use git -C <repo> push)"
    plan = (planned or {}).get(os.path.normpath(repo)) if not os.path.exists(repo) else None
    if plan:
        # The worktree does not exist yet. Read what it will hold, and tags in its repo.
        repo, current, upstream = plan["repo"], plan["branch"], plan["upstream"]
    elif git_out(repo, "rev-parse", "--git-dir") is None:
        return "git push outside a git repo (use git -C <repo> push)"
    else:
        current = git_out(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
        upstream = current and git_out(repo, "rev-parse", "--abbrev-ref", current + "@{upstream}")
        upstream = upstream and upstream.split("/", 1)[-1]
    refspecs = positional[1:]
    if not refspecs:
        # The target is the current branch's upstream, or the branch of the same name.
        if current is None:
            return "git push from a detached HEAD"
        targets = [current] + ([upstream] if upstream else [])
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


def allowed_here():
    """The publishing commands this machine has opted out of asking for."""
    names = {name.strip() for name in os.environ.get(ALLOW_VAR, "").split(",")}
    return names & OPTIONAL


ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)


def assigns(segment, variables):
    """Record `NAME=value` or `export NAME=value` standing alone, as in `R=~/dev/x; git -C $R push`.

    A value that still holds a `$` or a backtick is unknown, and stays unexpanded where it is used.
    """
    tokens = words(segment)
    if tokens and tokens[0] == "export":
        tokens = tokens[1:]
    found = len(tokens) == 1 and ASSIGNMENT.match(tokens[0])
    if not found:
        return False
    value = found.group(2)
    variables[found.group(1)] = None if "$" in value or "`" in value else value
    return True


def expand(segment, variables):
    """Fill in the variables this command set itself. Others stay as they are."""
    def known(match):
        value = variables.get(match.group(1) or match.group(2))
        return match.group(0) if value is None else shlex.quote(value)
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", known, segment)


def is_cd(segment):
    tokens = strip_prefix(words(segment))
    return bool(tokens) and tokens[0] in CHANGES_DIR


def cd_target(segment, cwd):
    """The folder after this `cd`, or None when the guard cannot tell.

    A later push from None asks, so every case that is not a plain path errs that way:
    a variable, `cd -`, `popd`, a folder that does not exist, and a `cd` inside a
    subshell, which only lasts until its closing parenthesis.
    """
    raw = words(segment)
    tokens = strip_prefix(list(raw))
    if "(" in raw[: len(raw) - len(tokens)] or cwd is None:
        return None
    args = [t for t in tokens[1:] if (t == "-" or not t.startswith("-")) and t not in GROUPING]
    if tokens[0] == "popd" or len(args) > 1 or args == ["-"]:
        return None
    if not args:
        return os.path.expanduser("~")
    if any(ch in args[0] for ch in "$`*?"):
        return None
    target = os.path.normpath(os.path.join(cwd, os.path.expanduser(args[0])))
    return target if os.path.isdir(target) else None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.getcwd()
    allowed = allowed_here()

    variables = {}
    planned = {}
    for segment in segments(command):
        segment = expand(segment, variables)
        if assigns(segment, variables):
            continue
        if is_cd(segment):
            cwd = cd_target(segment, cwd)
            continue
        worktree = planned_worktree(segment, cwd)
        if worktree:
            planned[worktree[0]] = worktree[1]
        reason = publishing_in(segment, cwd, planned)
        if reason and reason not in allowed:
            json.dump({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"W2: {reason} needs your approval.",
            }}, sys.stdout)
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
