#!/usr/bin/env python3
"""Flag comment bloat in Rust files.

Standalone:    python3 comment_lint.py src/foo.rs src/bar.rs
Your own work: python3 comment_lint.py --changed        (what you changed against HEAD)
Whole tree:    python3 comment_lint.py $(git ls-files '*.rs')
Stricter:      python3 comment_lint.py --changed --max-run 2
As a hook:     python3 comment_lint.py --hook   (reads the Claude Code hook JSON on stdin)

Findings come at two levels, because precision differs per rule:

- block: banners, step narration, change history, new /* */ blocks. Near 100% precision on
  real Jitter code, so the hook returns 2 and the agent fixes them in the same turn.
- advise: a long run of // lines (R3). There is no right number here, so it never interrupts
  an edit. Run it on your own work and pick a threshold to suit: 2 after writing a lot of
  prose, the default 4 normally, higher when every hit turns out to be worth keeping.

A line that has a good reason to break a rule says so:  // jitter-lint: allow R3 <reason>

Exit codes: 0 clean or advisory only, 1 findings (standalone), 2 blocking findings (--hook).
Runs on Linux and macOS with a stock python3, no dependencies.
"""

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

MAX_COMMENT_RUN = 4  # the default for R3, override with --max-run
IGNORE_FILE = ".jitter-lint-ignore"  # optional, one glob per line, for vendored trees

ALLOW_MARKER = re.compile(r"jitter-lint:\s*allow\s+([A-Z]\d+)")
# A SAFETY justification is required by convention and by clippy, and it is never bloat.
EXEMPT_RUN = re.compile(r"^\s*//[/!]?\s*(SAFETY|INVARIANT)\b", re.IGNORECASE)

# Doc comments are markdown, where --- is a horizontal rule, so banners are only // and /* */.
BANNER = re.compile(r"^\s*(//(?![/!])|/?\*+/?)\s*[=*#~_-]{4,}\s*$|^\s*/{5,}\s*$")
STEP_NARRATION = re.compile(r"^\s*//[/!]?\s*step\s*\d+\b", re.IGNORECASE)
# "Step 4 of the datasheet power-up sequence" is a cross-reference, not narration.
STEP_REFERENCE = re.compile(
    r"\b(datasheet|data sheet|reference manual|errata|app note|application note)\b",
    re.IGNORECASE,
)
CHANGE_HISTORY = re.compile(
    r"\b(used to be|used to have|used to use|we used to|this used to|it used to|"
    r"changed from|renamed from|now uses .* instead|instead of the old|replaced the old)\b",
    re.IGNORECASE,
)
LINE_COMMENT = re.compile(r"^\s*//(?![/!])")
DOC_COMMENT = re.compile(r"^\s*///(?!/)")
RAW_STRING = re.compile(r'r(#*)"')
CHAR_LITERAL = re.compile(r"'(\\.|[^\\'])'")

BLOCK = "block"
ADVISE = "advise"


def scan(path, max_run=MAX_COMMENT_RUN):
    """Findings as (start_line, end_line, rule, severity, message)."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [(1, 1, "IO", BLOCK, "could not read: {}".format(exc))]

    blocks, string_lines, comment_at = lex(lines)
    findings = (
        scan_runs(lines, max_run)
        + scan_blocks(blocks)
        + scan_patterns(lines, blocks, string_lines, comment_at)
    )
    allowed = allow_markers(lines)
    return sorted(f for f in findings if not suppressed(f, allowed))


def allow_markers(lines):
    """{line index: rule id} for every `jitter-lint: allow R3 <reason>` marker."""
    markers = {}
    for i, line in enumerate(lines):
        found = ALLOW_MARKER.search(line)
        if found:
            markers[i] = found.group(1)
    return markers


def suppressed(finding, allowed):
    """A marker anywhere inside the span the finding covers, or on the line above it."""
    start, end, rule = finding[0], finding[1], finding[2]
    return any(
        allowed_rule == rule and start - 2 <= index <= end - 1
        for index, allowed_rule in allowed.items()
    )


def lex(lines):
    """Walk the file once and report the block comment spans, the lines a string covers, and
    where a // comment starts on each line.

    Per-line scanning is not enough: strings span lines (raw strings, and regular ones
    continued with a backslash), a `*/` inside one used to look like a comment, and a char
    literal holding a quote used to swallow the rest of the file.
    """
    text = "\n".join(lines)
    regions = []
    string_lines = set()
    comment_at = {}
    line = 0
    depth = 0
    start_line = 0
    i = 0
    size = len(text)

    def mark(first, last):
        string_lines.update(range(first, last + 1))

    while i < size:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue

        if depth:
            if text.startswith("/*", i):
                depth += 1
                i += 2
                continue
            if text.startswith("*/", i):
                depth -= 1
                i += 2
                if depth == 0:
                    regions.append((start_line, line))
                continue
            i += 1
            continue

        if text.startswith("//", i):
            newline = text.find("\n", i)
            comment_at.setdefault(line, i - (text.rfind("\n", 0, i) + 1))
            if newline == -1:
                break
            i = newline
            continue

        if text.startswith("/*", i):
            depth = 1
            start_line = line
            i += 2
            continue

        raw = RAW_STRING.match(text, i)
        if raw:
            terminator = '"' + raw.group(1)
            closing = text.find(terminator, raw.end())
            closing = size if closing == -1 else closing + len(terminator)
            first = line
            line += text.count("\n", i, closing)
            mark(first, line)
            i = closing
            continue

        if ch == "'":
            literal = CHAR_LITERAL.match(text, i)
            if literal:
                i = literal.end()
            else:
                i += 1  # a lifetime, such as 'a
            continue

        if ch == '"':
            first = line
            i += 1
            while i < size:
                if text[i] == "\\":
                    line += text.count("\n", i, i + 2)
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                if text[i] == "\n":
                    line += 1
                i += 1
            mark(first, line)
            continue

        i += 1

    if depth:
        regions.append((start_line, len(lines) - 1))
    return regions, string_lines, comment_at


def scan_blocks(blocks):
    """R17, one finding per block so the hook can tell a new block from an old one."""
    return [
        (
            start + 1,
            end + 1,
            "R17",
            BLOCK,
            "R17: /* */ comment block of {} line(s). Rust comments are // and ///, and a "
            "C-style block is where banners and step narration come back.".format(end - start + 1),
        )
        for start, end in blocks
    ]


def as_comment(line):
    """A line inside a /* */ block, rewritten as a // line so the same patterns apply."""
    return re.sub(r"^\s*(/\*+|\*+/?)\s?", "// ", line)


def scan_runs(lines, max_run=MAX_COMMENT_RUN):
    """R3: a long run of // lines. A blank line does not reset the run, and a SAFETY or
    INVARIANT justification is exempt because it is required elsewhere."""
    findings = []
    start = last = None
    exempt = False

    def flush():
        if start is None or exempt:
            return
        length = sum(1 for i in range(start, last + 1) if LINE_COMMENT.match(lines[i]))
        if length > max_run:
            findings.append(
                (
                    start + 1,
                    last + 1,
                    "R3",
                    ADVISE,
                    "R3: {} comment lines in one run (over {}). Check they say why rather than "
                    "what, and keep them if they do.".format(length, max_run),
                )
            )

    for i, line in enumerate(lines):
        if LINE_COMMENT.match(line):
            if start is None:
                start = i
                exempt = bool(EXEMPT_RUN.match(line))
            last = i
        elif line.strip() == "" and start is not None:
            continue
        else:
            flush()
            start = last = None
            exempt = False
    flush()
    return findings


def scan_patterns(lines, blocks, string_lines=frozenset(), comment_at=None):
    comment_at = comment_at or {}
    inside = {i for start, end in blocks for i in range(start, end + 1)}
    findings = []
    for i, raw in enumerate(lines, start=1):
        index = i - 1
        if index in string_lines and index not in inside:
            if index not in comment_at:
                continue  # text inside a string literal is data, not a comment
            raw = " " * comment_at[index] + raw[comment_at[index]:]  # judge only the comment
        line = as_comment(raw) if index in inside else raw
        # A block can open after code, so also read it from the /* onward.
        variants = [line]
        if index in inside and "/*" in raw:
            variants.append(as_comment(raw[raw.index("/*"):]))
        if BANNER.match(raw) or (index in inside and any(BANNER.match(v) for v in variants)):
            findings.append(
                (i, i, "R2", BLOCK, "R2: banner comment. Delete it, the item name is the heading.")
            )
        elif any(STEP_NARRATION.match(v) for v in variants) and not STEP_REFERENCE.search(line):
            findings.append(
                (i, i, "R2", BLOCK, "R2: step narration. The code already shows the order.")
            )
        elif (LINE_COMMENT.match(line) or DOC_COMMENT.match(line)) and CHANGE_HISTORY.search(line):
            findings.append(
                (i, i, "R2", BLOCK, "R2: change history in a comment. Git records that.")
            )
        elif index not in inside and comment_at.get(index):
            # A comment after code on the same line, which the anchored patterns never see.
            # The column comes from the lexer, so a string earlier on the line does not matter.
            text = raw[comment_at[index]:]
            if text.startswith("//"):
                if STEP_NARRATION.match(text) and not STEP_REFERENCE.search(text):
                    findings.append(
                        (i, i, "R2", BLOCK, "R2: step narration. The code already shows the order.")
                    )
                elif CHANGE_HISTORY.search(text):
                    findings.append(
                        (i, i, "R2", BLOCK, "R2: change history in a comment. Git records that.")
                    )
    return findings


def ignore_globs(start):
    """Globs from the nearest .jitter-lint-ignore, walking up from the file."""
    here = Path(start).resolve().parent
    for folder in [here, *here.parents]:
        candidate = folder / IGNORE_FILE
        if candidate.is_file():
            globs = [
                line.strip()
                for line in candidate.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            return folder, globs
        if (folder / ".git").exists():
            break
    return None, []


def ignored(path):
    root, globs = ignore_globs(path)
    if not globs:
        return False
    try:
        rel = Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return False
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def written_spans(path, tool_input):
    """Line ranges this edit wrote, located by position.

    Matching on comment text alone blames an identical comment elsewhere in the file, and
    duplicated comment lines are common, so find where the written text actually sits.
    """
    chunks = [tool_input.get("new_string"), tool_input.get("content")]
    for edit in tool_input.get("edits") or []:
        chunks.append(edit.get("new_string"))
    chunks = [c for c in chunks if isinstance(c, str) and c.strip()]
    if not chunks:
        return []

    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    spans = []
    for chunk in chunks:
        found = False
        offset = text.find(chunk)
        while offset != -1:
            first = text.count("\n", 0, offset) + 1
            spans.append((first, first + chunk.rstrip("\n").count("\n")))
            found = True
            offset = text.find(chunk, offset + 1)
        if not found:
            # Whitespace differed, fall back to the written lines themselves.
            all_lines = [line.strip() for line in text.splitlines()]
            wanted = {line.strip() for line in chunk.splitlines() if line.strip()}
            for number, line in enumerate(all_lines, start=1):
                if line in wanted and all_lines.count(line) == 1:
                    spans.append((number, number))
    return spans


def in_spans(finding, spans):
    start, end = finding[0], finding[1]
    return any(not (end < low or start > high) for low, high in spans)


def changed_files():
    """Rust files this working tree changed against HEAD, staged or not."""
    done = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return [line for line in done.stdout.splitlines() if line.endswith(".rs")]


def main(argv):
    hook_mode = "--hook" in argv
    max_run = MAX_COMMENT_RUN
    skip = set()
    if "--max-run" in argv:
        index = argv.index("--max-run") + 1
        if index >= len(argv) or not argv[index].isdigit():
            sys.stderr.write("--max-run needs a number, for example --max-run 2\n")
            return 2
        max_run = int(argv[index])
        skip.add(index)
    paths = [a for i, a in enumerate(argv) if not a.startswith("-") and i not in skip]
    if "--changed" in argv:
        paths = changed_files()
    spans = {}

    if hook_mode:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0
        tool_input = payload.get("tool_input") or {}
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        paths = [path] if path else []
        if path:
            spans[path] = written_spans(path, tool_input)

    paths = [p for p in paths if p and p.endswith(".rs") and not ignored(p)]
    if not paths:
        return 0

    blocking, advisory = [], []
    for path in paths:
        for finding in scan(path, max_run):
            if hook_mode and not in_spans(finding, spans.get(path, [])):
                continue
            line = "{}:{}: {}".format(path, finding[0], finding[4])
            (blocking if finding[3] == BLOCK else advisory).append(line)

    if not hook_mode:
        for line in blocking + advisory:
            sys.stdout.write(line + "\n")
        return 1 if blocking or advisory else 0

    if blocking:
        sys.stderr.write(
            "Comment check on the lines this edit wrote:\n"
            + "\n".join(blocking)
            + "\nFix these here. Leave comments you did not write alone (R5). If a rule is "
            "wrong for this spot, put `// jitter-lint: allow <rule> <reason>` in the comment "
            "it refers to.\n"
        )
        return 2
    # Advisory findings are not sent to the agent mid-edit. Measured on sensor-link, 30 of 30
    # long comment runs were worth keeping, so the interruption would only cost tokens. They
    # still show up in a sweep, where a human is reading.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
