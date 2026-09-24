#!/usr/bin/env python3
"""Flag comment bloat in Rust files.

Standalone:   python3 comment_lint.py src/foo.rs src/bar.rs
Whole tree:   python3 comment_lint.py $(git ls-files '*.rs')
As a hook:    python3 comment_lint.py --hook   (reads the Claude Code hook JSON on stdin)

Exit codes: 0 clean, 1 findings (standalone), 2 findings (--hook, so the agent sees them).
Runs on Linux and macOS with a stock python3, no dependencies.
"""

import fnmatch
import json
import re
import sys
from pathlib import Path

# Tune these against a real repo. Keep false positives near zero.
MAX_COMMENT_RUN = 4  # consecutive // lines
MAX_DOC_RUN = 12  # consecutive /// lines on a private item
MAX_COMMENT_RATIO = 0.4  # inline // lines / code lines inside one fn, needs --ratio
MIN_FN_LINES_FOR_RATIO = 12  # ignore short fns, the ratio is noise there

# The ratio check is off by default: it fires on data tables that carry one short why-comment
# per row, which is exactly the commenting we want. Enable it with --ratio for a one-off sweep.
IGNORE_FILE = ".jitter-lint-ignore"  # optional, one glob per line, for vendored trees
# A line that has a good reason to break a rule says so, and says why.
ALLOW_MARKER = re.compile(r"jitter-lint:\s*allow\s+([A-Z]\d+)")

BANNER = re.compile(r"^\s*(//[/!]?|/?\*+/?)\s*[=*#~_-]{4,}\s*$|^\s*/{5,}\s*$")
BLOCK_OPEN = re.compile(r"/\*")
BLOCK_CLOSE = re.compile(r"\*/")
# Only real narration. A numbered list of cases or invariants is fine.
STEP_NARRATION = re.compile(r"^\s*//[/!]?\s*step\s*\d+\b", re.IGNORECASE)
# Only phrasings that describe the code's past, not ordinary prose containing "used to".
CHANGE_HISTORY = re.compile(
    r"\b(used to be|used to have|used to use|we used to|this used to|it used to|"
    r"changed from|renamed from|now uses .* instead|instead of the old|replaced the old)\b",
    re.IGNORECASE,
)
LINE_COMMENT = re.compile(r"^\s*//(?![/!])")
DOC_COMMENT = re.compile(r"^\s*///(?!/)")
MODULE_DOC = re.compile(r"^\s*//!")
ATTRIBUTE = re.compile(r"^\s*(#\[|#!\[)")
PUB_ITEM = re.compile(r"^\s*(pub(\s*\([^)]*\))?\s+)")
FN_START = re.compile(r"^(\s*)(pub(\s*\([^)]*\))?\s+)?(async\s+|const\s+|unsafe\s+|extern\s+\S+\s+)*fn\s")


def scan(path, ratio=False):
    """Return a list of (line_number, message)."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [(1, "could not read: {}".format(exc))]

    blocks = block_regions(lines)
    findings = []
    allowed = allow_markers(lines)
    findings += scan_runs(lines)
    findings += scan_blocks(lines, blocks)
    findings += scan_patterns(lines, blocks)
    if ratio:
        findings += scan_fn_ratio(lines)
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
    """A marker covers the line it sits on and the 2 lines after it."""
    lineno, message = finding
    rule = message.split(":", 1)[0]
    for index, allowed_rule in allowed.items():
        if allowed_rule == rule and 0 <= index - (lineno - 1) <= 2:
            return True
    return False


def block_regions(lines):
    """Line indices covered by /* */ comments, as a list of (start, end) inclusive pairs.

    C-style blocks are how banner headers and step narration come back in after a rewrite,
    and the // checks never see them.
    """
    regions = []
    start = None
    for i, line in enumerate(lines):
        # Only a comment that starts its own line counts. Anything else is usually a string,
        # such as an HTTP header `Accept: */*` in the middle of a raw literal.
        if start is None and BLOCK_OPEN.match(line.lstrip()):
            start = i
        if start is not None and BLOCK_CLOSE.search(line, 1 if start == i else 0):
            regions.append((start, i))
            start = None
    if start is not None:
        regions.append((start, len(lines) - 1))
    return regions


def scan_blocks(lines, blocks):
    """R17: Rust comments are // and ///, not /* */."""
    if not blocks:
        return []
    lines_covered = sum(end - start + 1 for start, end in blocks)
    return [
        (
            blocks[0][0] + 1,
            "R17: {} /* */ comment block(s), {} lines. Rust comments are // and ///, and a "
            "C-style block is where banners and step narration come back.".format(
                len(blocks), lines_covered
            ),
        )
    ]


def as_comment(line):
    """A line inside a /* */ block, rewritten as a // line so the same patterns apply."""
    return re.sub(r"^\s*(/\*+|\*+/?)\s?", "// ", line)


def scan_runs(lines):
    """Consecutive // blocks that are too long, and oversized /// on private items."""
    findings = []
    start = None
    kind = None

    def flush(end):
        if start is None:
            return
        length = end - start
        if kind == "//" and length > MAX_COMMENT_RUN:
            findings.append(
                (
                    start + 1,
                    "R3: {} consecutive // lines (max {}). Say why, not what, or move the "
                    "explanation to docs/decisions/ (R4).".format(length, MAX_COMMENT_RUN),
                )
            )
        if kind == "doc" and length > MAX_DOC_RUN:
            item = next_item(lines, end)
            if not PUB_ITEM.match(item):
                findings.append(
                    (
                        start + 1,
                        "R12: {} doc-comment lines on a private item (max {}). Keep the summary, "
                        "drop the rest.".format(length, MAX_DOC_RUN),
                    )
                )

    for i, line in enumerate(lines):
        if MODULE_DOC.match(line):
            this = None  # module docs may be as long as they need to be
        elif DOC_COMMENT.match(line):
            this = "doc"
        elif LINE_COMMENT.match(line):
            this = "//"
        else:
            this = None
        if this != kind:
            flush(i)
            kind = this
            start = i if this else None
    flush(len(lines))
    return findings


def next_item(lines, index):
    """First real line at or after index, skipping attributes and blanks."""
    for line in lines[index:]:
        if line.strip() and not ATTRIBUTE.match(line):
            return line
    return ""


def scan_patterns(lines, blocks=()):
    inside = {i for start, end in blocks for i in range(start, end + 1)}
    findings = []
    for i, raw in enumerate(lines, start=1):
        line = as_comment(raw) if i - 1 in inside else raw
        if BANNER.match(raw) or (i - 1 in inside and BANNER.match(line)):
            findings.append((i, "R2: banner comment. Delete it, the item name is the heading."))
        elif STEP_NARRATION.match(line):
            findings.append((i, "R2: step narration. The code already shows the order."))
        elif (LINE_COMMENT.match(line) or DOC_COMMENT.match(line)) and CHANGE_HISTORY.search(line):
            findings.append((i, "R2: change history in a comment. Git records that."))
    return findings


def scan_fn_ratio(lines):
    """Comment-to-code ratio per fn body, using brace depth from the fn signature."""
    findings = []
    i = 0
    while i < len(lines):
        if not FN_START.match(lines[i]):
            i += 1
            continue
        depth = 0
        opened = False
        comments = 0
        code = 0
        start = i
        j = i
        while j < len(lines):
            line = lines[j]
            stripped = strip_strings(line)
            # Doc comments are wanted, only inline // count against the ratio.
            if LINE_COMMENT.match(line):
                comments += 1
            elif line.strip() and not DOC_COMMENT.match(line) and not MODULE_DOC.match(line):
                code += 1
            depth += stripped.count("{") - stripped.count("}")
            if "{" in stripped:
                opened = True
            if opened and depth <= 0:
                break
            j += 1
        total = j - start + 1
        if total >= MIN_FN_LINES_FOR_RATIO and code and comments / code > MAX_COMMENT_RATIO:
            findings.append(
                (
                    start + 1,
                    "R2: {} comment lines to {} code lines in this fn. Cut the ones that restate "
                    "the code.".format(comments, code),
                )
            )
        i = max(j, i) + 1
    return findings


def strip_strings(line):
    """Drop string and char literals, and the trailing // comment, so what is left is code."""
    out = []
    quote = None
    k = 0
    while k < len(line):
        ch = line[k]
        if quote:
            if ch == "\\":
                k += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "/" and k + 1 < len(line) and line[k + 1] == "/":
            break
        else:
            out.append(ch)
        k += 1
    return "".join(out)


COMMENTISH = re.compile(r"^\s*(//|/\*|\*)")


def in_edit(lines, lineno, message, touched):
    """Did this edit write the comment the finding is about?

    A run or block finding points at its first line, so walk the run itself. Only comment
    lines count: editing the code under someone else's comment block is not writing it (R5).
    """
    index = lineno - 1
    if not (0 <= index < len(lines)):
        return False
    if not message.startswith(("R3", "R12", "R17")):
        return lines[index].strip() in touched
    while index < len(lines) and COMMENTISH.match(lines[index]):
        if lines[index].strip() in touched:
            return True
        index += 1
    return False


def ignore_globs(start):
    """Globs from the nearest .jitter-lint-ignore, walking up from the file."""
    here = Path(start).resolve().parent
    for folder in [here, *here.parents]:
        candidate = folder / IGNORE_FILE
        if candidate.is_file():
            globs = []
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    globs.append(line)
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


def written_lines(tool_input):
    """The comment lines this edit actually wrote, as a set of stripped texts.

    Findings are filtered against it in hook mode, so an edit is judged on what it added,
    never on comments someone else wrote elsewhere in the file (R5).
    """
    texts = set()
    chunks = [tool_input.get("new_string"), tool_input.get("content")]
    for edit in tool_input.get("edits") or []:
        chunks.append(edit.get("new_string"))
    for chunk in chunks:
        if isinstance(chunk, str):
            texts.update(line.strip() for line in chunk.splitlines() if line.strip())
    return texts


def main(argv):
    hook_mode = "--hook" in argv
    ratio = "--ratio" in argv
    paths = [a for a in argv if not a.startswith("-")]
    touched = None

    if hook_mode:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0
        tool_input = payload.get("tool_input") or {}
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        paths = [path] if path else []
        touched = written_lines(tool_input)

    paths = [p for p in paths if p and p.endswith(".rs") and not ignored(p)]
    if not paths:
        return 0

    report = []
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for line, message in scan(path, ratio=ratio):
            if touched is not None and not in_edit(lines, line, message, touched):
                continue
            report.append("{}:{}: {}".format(path, line, message))

    if not report:
        return 0

    if hook_mode:
        sys.stderr.write(
            "Comment check on what this edit wrote, Jitter rules R2 to R5, R12 and R17:\n"
            + "\n".join(report)
            + "\nFix these in the lines you just wrote. Leave the rest of the file alone (R5).\n"
        )
        return 2

    sys.stdout.write("\n".join(report) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
