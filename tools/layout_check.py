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


def ignore_globs(start):
    """Globs from the nearest .jitter-lint-ignore, walking up from the file, as comment_lint does."""
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
