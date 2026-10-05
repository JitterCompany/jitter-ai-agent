#!/usr/bin/env python3
"""Run every `run:` step of .github/workflows/ci.yml locally, in order.

    python3 tools/ci_local.py

Reads the workflow instead of repeating it, so it cannot drift from what CI runs.
Exits 1 when a step fails. Needs PyYAML.
"""

import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ci_local.py needs PyYAML: pip3 install --user pyyaml")

ROOT = Path(__file__).resolve().parent.parent


def main():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    failed = []
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "run" not in step:
                continue
            name = step.get("name", step["run"].splitlines()[0])
            done = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=ROOT, capture_output=True, text=True)
            print(("PASS" if done.returncode == 0 else "FAIL"), name)
            if done.returncode:
                print((done.stdout + done.stderr).rstrip())
                failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
