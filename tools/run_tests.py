#!/usr/bin/env python3
"""Self-test for the checks in this repo. Run it after changing a threshold or a pattern.

    python3 tools/run_tests.py

A check that fires on good code is worse than one that misses, so most cases here are things
that must stay silent. Every case a review found broken has a test named after it.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent

GOOD_RUST = '''\
//! Slot lookup, a module doc may be as long as it needs to be.
//! line two
//! line three

/// Powers the modem and waits until it accepts AT commands.
pub async fn power_up(&mut self) -> Result<(), Error> {
    self.enable.set_high();
    // BG95 needs 3s from enable to first AT response, 2s is not enough.
    Timer::after(BOOT_DELAY).await;
    self.uart.open()
}

// SAFETY: the peripheral is owned here, the DMA controller only writes the buffer
// between start() and the transfer-complete interrupt, both of which live in this
// module, and the buffer sits in the same struct so it outlives the transfer.
// No other reference to it can exist while the transfer runs, which is what the
// unsafe impl below promises.
unsafe impl Send for Dma {}

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

const HEADERS: &str = "GET / HTTP/1.1\\r\\n\\
     Accept: */*\\r\\n\\
     Connection: keep-alive\\r\\n\\r\\n";
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

# Built at runtime so this file does not itself trip path_leak_check.
LEAKY = 'path = "/{}/alice/dev/x"\nmail = "alice.private@{}.com"\n'.format("home", "gmail")
CLEAN_PATHS = 'path = "${KIPRJMOD}/../x"\nmail = "dev@jitter.company"\nhome = "/home/user/generic"\n'

PROJECT = {
    "erc": {"erc_exclusions": ["a", "b"], "rule_severities": {"x": "ignore"}},
    "board": {"design_settings": {"drc_exclusions": ["a", "b", "c"], "rule_severities": {}}},
}


def run(tool, args, cwd=None, stdin=None):
    done = subprocess.run(
        [sys.executable, str(TOOLS / tool), *args],
        cwd=cwd, input=stdin, capture_output=True, text=True, check=False,
    )
    return done.returncode, done.stdout + done.stderr


def hook(tool, payload):
    return run(tool, ["--hook"], stdin=json.dumps(payload))


def edit(path, new_string):
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": new_string}}


def git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def check(name, condition, detail=""):
    print("{} {}{}".format("PASS" if condition else "FAIL", name, "" if condition else "\n     " + detail.strip()))
    return condition


def comment_lint_cases(tmp, ok):
    good = tmp / "good.rs"
    good.write_text(GOOD_RUST)
    code, out = run("comment_lint.py", [str(good)])
    ok &= check("silent on good code, including SAFETY and a continued string", code == 0, out)

    bloat = tmp / "bloat.rs"
    bloat.write_text(BLOATED_RUST)
    code, out = run("comment_lint.py", [str(bloat)])
    ok &= check("flags banners, narration and change history", code == 1 and out.count("R2") >= 3, out)

    wrote_it = hook("comment_lint.py", edit(bloat, "    // Step 1: walk the vector\n"))
    ok &= check("hook exits 2 on what this edit wrote", wrote_it[0] == 2, wrote_it[1])

    elsewhere = hook("comment_lint.py", edit(bloat, "pub const LIMIT: usize = 8;\n"))
    ok &= check("hook silent about comments this edit did not write (R5)", elsewhere[0] == 0, elsewhere[1])

    cross = tmp / "cross.rs"
    cross.write_text("fn old() {\n" + "    // note\n" * 6 + "}\n\nfn new() {\n    // note\n    let x = 1;\n}\n")
    result = hook("comment_lint.py", edit(cross, "    // note\n    let x = 1;\n"))
    ok &= check("identical comment text elsewhere is not blamed", result[0] == 0, result[1])

    long_run = tmp / "long.rs"
    long_run.write_text("".join("// reason {}\n".format(i) for i in range(8)) + "fn x() {}\n")
    result = hook("comment_lint.py", edit(long_run, "// reason 0\n// reason 1\n"))
    ok &= check("a long run never interrupts an edit", result[0] == 0 and not result[1].strip(), result[1])
    code, out = run("comment_lint.py", [str(long_run)])
    ok &= check("a long run still shows up in a sweep", code == 1 and "R3" in out, out)

    split = tmp / "split.rs"
    split.write_text("// a\n// b\n// c\n// d\n\n// e\n// f\n// g\n// h\nfn x() {}\n")
    code, out = run("comment_lint.py", [str(split)])
    ok &= check("two runs split by a blank line still count as one", code == 1 and "R3" in out, out)

    marked = tmp / "marked.rs"
    marked.write_text(
        "// a\n// b\n// c\n// d\n// e\n// jitter-lint: allow R3 the derivation belongs here\nfn x() {}\n"
    )
    code, out = run("comment_lint.py", [str(marked)])
    ok &= check("an allow marker at the end of the run suppresses it", code == 0, out)

    blocks = tmp / "blocks.rs"
    blocks.write_text("/* old\n   block */\nfn a() {}\n\n/* new\n   block */\nfn b() {}\n")
    result = hook("comment_lint.py", edit(blocks, "/* new\n   block */\nfn b() {}\n"))
    ok &= check("a new /* */ block is seen next to an old one", result[0] == 2, result[1])

    charlit = tmp / "charlit.rs"
    charlit.write_text("fn q() { let c = \'\"\'; }\n/* a real block\n   two\n   three */\n")
    code, out = run("comment_lint.py", [str(charlit)])
    ok &= check("a char literal holding a quote does not blind the file", code == 1 and "R17" in out, out)

    template = tmp / "template.rs"
    template.write_text('const T: &str = r#"\n// =====================\n// Step 1: preamble\n"#;\n')
    code, out = run("comment_lint.py", [str(template)])
    ok &= check("comment-looking text inside a string is data", code == 0, out)

    datasheet = tmp / "datasheet.rs"
    datasheet.write_text(
        "// Step 4 of the datasheet power-up sequence, do not reorder.\npub fn up() {}\n\n"
        "/// ----\n/// A markdown rule in a doc comment.\npub fn doc() {}\n"
    )
    code, out = run("comment_lint.py", [str(datasheet)])
    ok &= check("a datasheet step and a markdown rule are not flagged", code == 0, out)

    escaped = tmp / "escaped.rs"
    backslash_quote = "'" + chr(92) + chr(34) + "'"  # the Rust char literal '\"'
    escaped.write_text(
        "fn a() {\n"
        "    let c = " + backslash_quote + ";\n"
        "    // =========================\n"
        '    let s = "text with /* x */";\n'
        "}\n"
    )
    code, out = run("comment_lint.py", [str(escaped)])
    ok &= check(
        "an escaped char literal does not desync the lexer",
        code == 1 and "R2" in out and "R17" not in out, out,
    )

    after_code = tmp / "after_code.rs"
    after_code.write_text(
        "foo(); // Step 2: enable the clock\n"
        "bar(); // this used to be 3ms\n"
        "baz(); // Step 4 of the datasheet sequence\n"
    )
    code, out = run("comment_lint.py", [str(after_code)])
    ok &= check(
        "a comment after code is checked, and a datasheet step is not narration",
        code == 1 and out.count("R2") == 2, out,
    )

    trailing = tmp / "trailing.rs"
    trailing.write_text("let x = 1; /* =====================\n   banner\n   ===================== */\n")
    code, out = run("comment_lint.py", [str(trailing)])
    ok &= check("a block comment after code is seen", code == 1 and "R17" in out, out)
    return ok


def path_leak_cases(tmp, ok):
    clean = tmp / "clean.toml"
    clean.write_text(CLEAN_PATHS)
    code, out = run("path_leak_check.py", [str(clean)])
    ok &= check("placeholders and team addresses are allowed", code == 0, out)

    leak = tmp / "leak.toml"
    leak.write_text(LEAKY)
    code, out = run("path_leak_check.py", [str(leak)])
    ok &= check("a real home path and a personal address are flagged", code == 1, out)

    keys = tmp / "keys.rs"
    keys.write_text('const HEADER: &str = "-----BEGIN EC PRIVATE KEY-----";\n')
    code, out = run("path_leak_check.py", [str(keys)])
    ok &= check("a PEM header constant is not a leak without key material", code == 0, out)

    modules = tmp / ".gitmodules"
    modules.write_text("\turl = git@github.com:JitterCompany/pcb_release.git\n")
    code, out = run("path_leak_check.py", [str(modules)])
    ok &= check("a git@ remote is not an email address", code == 0, out)
    return ok


def prose_cases(tmp, ok):
    written = tmp / "written.md"
    written.write_text("Clean line.\nA new line with an em dash \u2014 here.\n")
    result = hook("prose_check.py", {"tool_name": "Edit", "tool_input": {
        "file_path": str(written), "new_string": "A new line with an em dash \u2014 here.\n"}})
    ok &= check("prose hook blocks an em dash this edit wrote", result[0] == 2, result[1])

    old = tmp / "old.md"
    old.write_text("An old line with an em dash \u2014 here.\nNew line, clean.\n")
    result = hook("prose_check.py", {"tool_name": "Edit", "tool_input": {
        "file_path": str(old), "new_string": "New line, clean.\n"}})
    ok &= check("prose hook ignores a dash this edit did not write", result[0] == 0, result[1])

    code = tmp / "code.rs"
    code.write_text("// an em dash \u2014 in Rust is for the comment check, not this one\n")
    result = hook("prose_check.py", {"tool_name": "Edit", "tool_input": {
        "file_path": str(code), "new_string": "// an em dash \u2014 in Rust\n"}})
    ok &= check("prose hook only judges text files", result[0] == 0, result[1])

    doc = tmp / "prose.md"
    doc.write_text("A sentence with an em dash — like this.\nA range of 10–100 MHz is fine.\n")
    code, out = run("prose_check.py", [str(doc)])
    ok &= check("prose_check flags em dashes, allows numeric ranges", code == 1 and out.count("P1") == 1, out)
    return ok


def repo_cases(tmp, ok):
    repo = tmp / "repo"
    (repo / "hardware").mkdir(parents=True)
    git(["init", "-q", "-b", "main"], repo)

    project = repo / "hardware" / "board.kicad_pro"
    project.write_text(json.dumps(PROJECT, indent=2))
    (repo / "notes.md").write_text("clean\n")
    git(["add", "-A"], repo)
    git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], repo)

    code, out = run("kicad_project_check.py", [], cwd=repo)
    ok &= check("kicad_project_check quiet when nothing was dropped", code == 0, out)

    wiped = json.loads(project.read_text())
    wiped["erc"]["erc_exclusions"] = []
    project.write_text(json.dumps(wiped, indent=2))
    code, out = run("kicad_project_check.py", [], cwd=repo)
    ok &= check("kicad_project_check catches cleared exclusions", code == 1 and "erc_exclusions" in out, out)
    git(["checkout", "--", "hardware/board.kicad_pro"], repo)

    (repo / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03")
    git(["add", "img.png"], repo)
    code, out = run("path_leak_check.py", ["--staged"], cwd=repo)
    ok &= check("--staged survives a binary file in the commit", code == 0, out)

    (repo / "notes.md").write_text(LEAKY)
    git(["add", "notes.md"], repo)
    (repo / "notes.md").write_text("clean again\n")
    code, out = run("path_leak_check.py", ["--staged"], cwd=repo)
    ok &= check("--staged reads the index, not the worktree", code == 1, out)

    git(["checkout", "--", "notes.md"], repo)
    git(["reset", "-q"], repo)
    (repo / "notes.md").write_text(LEAKY)
    code, out = run("path_leak_check.py", ["--staged"], cwd=repo)
    ok &= check("--staged ignores an unstaged leak", code == 0, out)

    (repo / "src" / "thing").mkdir(parents=True)
    (repo / "src" / "thing" / "mod.rs").write_text("pub fn x() {}\n")
    (repo / "src" / "other.rs").write_text("pub fn y() {}\n")
    git(["add", "-A"], repo)
    code, out = run("layout_check.py", [], cwd=repo)
    ok &= check("layout_check finds mod.rs (R7)", code == 1 and "thing" in out, out)
    code, out = run("layout_check.py", [str(repo / "src" / "other.rs")], cwd=repo)
    ok &= check("layout_check quiet on a normal module", code == 0, out)

    (repo / ".jitter-lint-ignore").write_text("src/thing/*\n")
    code, out = run("layout_check.py", [], cwd=repo)
    ok &= check("layout_check honours .jitter-lint-ignore for a frozen tree", code == 0, out)
    (repo / ".jitter-lint-ignore").unlink()
    return ok


def guard_cases(ok):
    blocked = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": "git push -u origin HEAD"}})
    ok &= check("guard_push blocks an unapproved push (W2)", blocked[0] == 2, blocked[1])

    pr = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"}})
    ok &= check("guard_push blocks gh pr create", pr[0] == 2, pr[1])

    approved = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": "JITTER_PUSH_OK=1 git push"}})
    ok &= check("guard_push lets an approved push through", approved[0] == 0, approved[1])

    local = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x' && git status"}})
    ok &= check("guard_push ignores local git work", local[0] == 0, local[1])

    mention = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": 'grep -rn "git push" docs/'}})
    ok &= check("guard_push ignores a quoted mention of a push", mention[0] == 0, mention[1])

    dry = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": "git push --dry-run origin main"}})
    ok &= check("guard_push allows a dry run", dry[0] == 0, dry[1])

    for command, want, name in [
        ("git -C /repo push origin main", 2, "git -C is still a push"),
        ("sudo git push", 2, "sudo does not hide a push"),
        ("time git push origin main", 2, "time does not hide a push"),
        ("echo main | xargs git push origin", 2, "xargs does not hide a push"),
        ("(git push)", 2, "a subshell does not hide a push"),
        ("if true; then git push; fi", 2, "a then branch does not hide a push"),
        ("for x in a; do git push; done", 2, "a loop body does not hide a push"),
        ("echo $(git push)", 2, "command substitution does not hide a push"),
        ("/usr/bin/git push", 2, "an absolute path is still git"),
        ("echo 'careful; git push origin main'", 0, "a separator inside quotes is not a separator"),
        ("cargo publish --dry-run && git push origin main", 2, "a dry run elsewhere does not excuse a push"),
        ('echo "JITTER_PUSH_OK=1"; git push origin main', 2, "a quoted mention of the escape is not approval"),
        ("bash -c 'git push origin main'", 2, "a push inside bash -c is seen"),
        ("grep -rn git push docs/", 0, "an unquoted grep is not a push"),
        ('git commit -m "wip"   # then git push later', 0, "a trailing comment does not block the commit"),
        ("cat <<'EOF' > README.md\nrun git push when ready\nEOF", 0, "a heredoc body is data"),
    ]:
        result = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": command}})
        ok &= check("guard_push: " + name, result[0] == want, result[1])
    return ok


def main():
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ok = comment_lint_cases(tmp, ok)
        ok = path_leak_cases(tmp, ok)
        ok = prose_cases(tmp, ok)
        ok = repo_cases(tmp, ok)
        ok = guard_cases(ok)
    print("\n{}".format("all good" if ok else "something regressed"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
