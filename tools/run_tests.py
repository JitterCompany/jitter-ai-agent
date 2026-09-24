#!/usr/bin/env python3
"""Self-test for the checks in this repo. Run it after changing a threshold or a pattern.

    python3 tools/run_tests.py

Each case is (input, expected hit count). A check that fires on clean code is worse than one
that misses, so the clean cases matter most.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent

CLEAN_RUST = '''\
/// Powers the modem and waits until it accepts AT commands.
pub async fn power_up(&mut self) -> Result<(), Error> {
    self.enable.set_high();
    // BG95 needs 3s from enable to first AT response, 2s is not enough.
    Timer::after(BOOT_DELAY).await;
    self.uart.open()
}

/// One short why-comment per row is the commenting we want, not bloat.
pub fn park_all_outputs() {
    for (pin, state) in [
        // Rail off, nothing left driving an unpowered module.
        (MODEM_PWR_EN, Low),
        // Chip selects deasserted, so neither memory drives its bus.
        (FLASH_CS, High),
    ] {
        pin.park(state);
    }
}

//! A module doc may be as long as it needs to be, line 1
//! line 2
//! line 3
//! line 4
//! line 5
//! line 6
'''

BLOATED_RUST = '''\
// =========================================
// Helper
// =========================================
pub fn read(v: &Vec<u32>) -> i32 {
    // Step 1: walk the vector
    // this used to return 0 here
    // loop over every index
    // compare each element
    // return the index when found
    for i in 0..v.len() {
        if v[i] == 42 { return i as i32; }
    }
    -1
}
'''

LEAKY = 'path = "/home/alice/dev/x"\nmail = "alice.private@gmail.com"\n'
CLEAN_PATHS = 'path = "${KIPRJMOD}/../x"\nmail = "dev@jitter.company"\nhome = "/home/user/generic"\n'

PROJECT = {
    "erc": {"erc_exclusions": ["a", "b"], "rule_severities": {"x": "ignore"}},
    "board": {"design_settings": {"drc_exclusions": ["a", "b", "c"], "rule_severities": {}}},
    "text_variables": {},
}


def run(tool, args, cwd=None):
    done = subprocess.run(
        [sys.executable, str(TOOLS / tool), *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout + done.stderr


def git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def check(name, condition, detail=""):
    print("{} {}{}".format("PASS" if condition else "FAIL", name, "" if condition else "  " + detail))
    return condition


def main():
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        (tmp / "clean.rs").write_text(CLEAN_RUST)
        code, out = run("comment_lint.py", [str(tmp / "clean.rs")])
        ok &= check("comment_lint stays quiet on good code", code == 0, out)

        (tmp / "bloat.rs").write_text(BLOATED_RUST)
        code, out = run("comment_lint.py", [str(tmp / "bloat.rs")])
        hits = len(out.strip().splitlines())
        ok &= check("comment_lint flags banners, narration, history, long runs", code == 1 and hits >= 4, out)

        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(tmp / "bloat.rs")}})
        done = subprocess.run(
            [sys.executable, str(TOOLS / "comment_lint.py"), "--hook"],
            input=payload, capture_output=True, text=True, check=False,
        )
        ok &= check("comment_lint --hook exits 2 so the agent sees it", done.returncode == 2, done.stderr)

        (tmp / "clean.toml").write_text(CLEAN_PATHS)
        code, out = run("path_leak_check.py", [str(tmp / "clean.toml")])
        ok &= check("path_leak_check allows placeholders and team addresses", code == 0, out)

        (tmp / "leak.toml").write_text(LEAKY)
        code, out = run("path_leak_check.py", [str(tmp / "leak.toml")])
        ok &= check("path_leak_check flags a real home path and a personal address", code == 1 and out.count(":") >= 2, out)

        (tmp / "prose.md").write_text(
            "A sentence with an em dash \u2014 like this.\nA range of 10\u2013100 MHz is fine.\n"
        )
        code, out = run("prose_check.py", [str(tmp / "prose.md")])
        ok &= check("prose_check flags em dashes, allows numeric ranges", code == 1 and out.count("P1") == 1, out)

        repo = tmp / "repo"
        (repo / "hardware").mkdir(parents=True)
        project = repo / "hardware" / "board.kicad_pro"
        project.write_text(json.dumps(PROJECT, indent=2))
        git(["init", "-q", "-b", "main"], repo)
        git(["add", "-A"], repo)
        git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], repo)

        code, out = run("kicad_project_check.py", [], cwd=repo)
        ok &= check("kicad_project_check quiet when nothing was dropped", code == 0, out)

        wiped = json.loads(project.read_text())
        wiped["erc"]["erc_exclusions"] = []
        wiped["board"]["design_settings"]["drc_exclusions"] = ["a"]
        project.write_text(json.dumps(wiped, indent=2))
        code, out = run("kicad_project_check.py", [], cwd=repo)
        ok &= check("kicad_project_check catches cleared exclusions", code == 1 and "erc_exclusions" in out, out)

    print("\n{}".format("all good" if ok else "something regressed"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
