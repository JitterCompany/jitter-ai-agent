#!/usr/bin/env python3
"""Check the Rust layout rules that are decidable from filenames alone.

    python3 layout_check.py                 # every tracked file in this repo
    python3 layout_check.py src/foo/mod.rs

R7: a module with submodules is `mything.rs` beside `mything/`, never `mything/mod.rs`.
Exit 0 clean, 1 findings. Linux and macOS, stock python3.
"""

import subprocess
import sys
from pathlib import Path


def tracked():
    done = subprocess.run(["git", "ls-files", "*.rs"], capture_output=True, text=True, check=False)
    return [line for line in done.stdout.splitlines() if line]


def main(argv):
    paths = [a for a in argv if not a.startswith("-")] or tracked()
    findings = []
    for path in paths:
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
