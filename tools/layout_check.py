#!/usr/bin/env python3
"""Check the Rust layout rules that are decidable from filenames alone.

    python3 layout_check.py                 # every tracked file in this repo
    python3 layout_check.py src/foo/mod.rs

R7: a module with submodules is `mything.rs` beside `mything/`, never `mything/mod.rs`.
Exit 0 clean, 1 findings. Linux and macOS, stock python3.
"""

import fnmatch
import subprocess
import sys
from pathlib import Path

IGNORE_FILE = ".jitter-lint-ignore"  # one glob per line, for vendored or frozen trees


def tracked():
    done = subprocess.run(["git", "ls-files", "*.rs"], capture_output=True, text=True, check=False)
    return [line for line in done.stdout.splitlines() if line]


def ignored(path):
    """Globs from .jitter-lint-ignore at the repo root, the same file comment_lint reads."""
    root = Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    ).stdout.strip() or ".")
    candidate = root / IGNORE_FILE
    if not candidate.is_file():
        return False
    globs = [
        line.strip()
        for line in candidate.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    try:
        rel = Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def main(argv):
    paths = [a for a in argv if not a.startswith("-")] or tracked()
    findings = []
    for path in paths:
        if ignored(path):
            continue
        p = Path(path)
        if p.name != "mod.rs":
            continue
        findings.append(
            "{}: R7: rename to {}.rs beside the {}/ folder, and drop this file.".format(
                path, p.parent.name, p.parent.name
            )
        )

    if not findings:
        return 0
    sys.stderr.write("\n".join(findings) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
