#!/usr/bin/env python3
"""Self-test for the checks in this repo. Run it after changing a threshold or a pattern.

    python3 tools/run_tests.py

A check that fires on good code is worse than one that misses, so most cases here are things
that must stay silent. Every case a review found broken has a test named after it.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
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

    # A blocking finding in one place, and the same comment text written somewhere else.
    cross = tmp / "cross.rs"
    cross.write_text(
        "fn old() {\n    // Step 1: the old narration\n    let a = 1;\n}\n\n"
        "fn new() {\n    let a = 1;\n}\n"
    )
    result = hook("comment_lint.py", edit(cross, "    let a = 1;\n"))
    ok &= check("identical code elsewhere does not drag in a blocking finding", result[0] == 0, result[1])
    result = hook("comment_lint.py", edit(cross, "    // Step 1: the old narration\n"))
    ok &= check("the edit that wrote the narration is blocked", result[0] == 2, result[1])

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

    # Contract: the threshold is 4, so 4 is silent and 5 speaks. A test that only uses an
    # 8-line run passes for any threshold from 1 to 7, which is how a threshold change slips by.
    at_limit = tmp / "at_limit.rs"
    at_limit.write_text("// a\n// b\n// c\n// d\nfn x() {}\n")
    code, out = run("comment_lint.py", [str(at_limit)])
    ok &= check("a run of exactly 4 is silent", code == 0, out)

    over_limit = tmp / "over_limit.rs"
    over_limit.write_text("// a\n// b\n// c\n// d\n// e\nfn x() {}\n")
    code, out = run("comment_lint.py", [str(over_limit)])
    ok &= check("a run of 5 is reported", code == 1 and "R3" in out, out)

    code, out = run("comment_lint.py", ["--max-run", "6", str(over_limit)])
    ok &= check("--max-run loosens the threshold", code == 0, out)
    code, out = run("comment_lint.py", ["--max-run", "2", str(at_limit)])
    ok &= check("--max-run tightens it", code == 1 and "R3" in out, out)
    code, out = run("comment_lint.py", ["--max-run", "x", str(at_limit)])
    ok &= check("--max-run rejects a non-number", code == 2, out)

    # Contract: four fill characters make a banner.
    short_banner = tmp / "short_banner.rs"
    short_banner.write_text("// ====\nfn x() {}\n")
    code, out = run("comment_lint.py", [str(short_banner)])
    ok &= check("four fill characters are already a banner", code == 1 and "R2" in out, out)

    # The marker sits on the line above the run, not inside it, so the window matters.
    above = tmp / "above.rs"
    above.write_text(
        "/// jitter-lint: allow R3 the derivation belongs here\n"
        + "".join("// line {}\n".format(i) for i in range(6))
        + "fn x() {}\n"
    )
    code, out = run("comment_lint.py", [str(above)])
    ok &= check("an allow marker on the line above the run works", code == 0, out)

    trailing = tmp / "trailing.rs"
    trailing.write_text("let x = 1; /* =====================\n   banner\n   ===================== */\n")
    code, out = run("comment_lint.py", [str(trailing)])
    ok &= check(
        "a block comment after code is seen, banner included",
        code == 1 and "R17" in out and "R2" in out, out,
    )

    with_strings = tmp / "with_strings.rs"
    with_strings.write_text(
        'info!("starting"); // Step 3: kick the modem\n'
        'let s = "x";       // this used to be 5ms\n'
        'let v = "// Step 9: inside a string";\n'
    )
    code, out = run("comment_lint.py", [str(with_strings)])
    ok &= check(
        "a trailing comment is checked even when the line holds a string",
        code == 1 and out.count("R2") == 2, out,
    )
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

    # Assembled at runtime so this file does not trip the check it is testing.
    real_key = tmp / "key.pem"
    real_key.write_text(
        "-----BEGIN EC PRIVATE {}-----".format("KEY")
        + "MHcCAQEEIBvQ1Z8mS0Yk9dR3pL7wX2nT4uC6eA8fG0hJ1kM3nP5qoAoGCCqGSM49\n"
    )
    code, out = run("path_leak_check.py", [str(real_key)])
    ok &= check("a PEM header with key material after it is a leak", code == 1, out)

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
    ok &= check("P1 blocks an em dash this edit wrote", result[0] == 2, result[1])

    old = tmp / "old.md"
    old.write_text("An old line with an em dash \u2014 here.\nNew line, clean.\n")
    result = hook("prose_check.py", {"tool_name": "Edit", "tool_input": {
        "file_path": str(old), "new_string": "New line, clean.\n"}})
    ok &= check("P1 ignores a dash this edit did not write", result[0] == 0, result[1])

    rust = tmp / "code.rs"
    rust.write_text("// an em dash \u2014 in Rust is the comment check's business\n")
    result = hook("prose_check.py", {"tool_name": "Edit", "tool_input": {
        "file_path": str(rust), "new_string": "// an em dash \u2014 in Rust\n"}})
    ok &= check("the prose hook only judges text files", result[0] == 0, result[1])

    doc = tmp / "prose.md"
    doc.write_text("A sentence with an em dash \u2014 like this.\nA range of 10\u2013100 MHz is fine.\n")
    code, out = run("prose_check.py", [str(doc)])
    ok &= check("P1 flags em dashes, allows numeric ranges", code == 1 and out.count("P1") == 1, out)

    en_dash = tmp / "en_dash.md"
    en_dash.write_text("A range of 10\u2013100 MHz is fine, a pause \u2013 like this \u2013 is not.\n")
    code, out = run("prose_check.py", [str(en_dash)])
    ok &= check("an en dash used as punctuation is P1", code == 1 and "P1" in out, out)

    marked = tmp / "marked.md"
    marked.write_text("A quoted dash \u2014 kept. prose-check: allow\n")
    code, out = run("prose_check.py", [str(marked)])
    ok &= check("the prose allow marker works", code == 0, out)

    fenced = tmp / "fenced.md"
    fenced.write_text(
        "````markdown\n```\nA fence inside a fence \u2014 still code.\n```\n````\n\n"
        "~~~c\nint x; /* a tilde fence \u2014 also code */\n~~~\n\n"
        "Inline `a \u2014 b` code is fine.\n\n    indented \u2014 code is fine\n"
    )
    code, out = run("prose_check.py", [str(fenced)])
    ok &= check("nested fences, tilde fences, inline and indented code are not prose", code == 0, out)

    underline = tmp / "section.rst"
    underline.write_text("Heading\n~~~~~~~\n\nA line with an em dash \u2014 here.\n")
    code, out = run("prose_check.py", [str(underline)])
    ok &= check("an rst section underline is not a code fence", code == 1 and "P1" in out, out)

    judgement = tmp / "judgement.md"
    judgement.write_text(
        "Init the driver before the measurement task starts and nothing else runs; "
        "otherwise the first conversion returns stale data.\n"
        "An aside (the pinned toolchain; see rustup) is not two sentences welded together.\n"
        "| a | b; c is a table cell with plenty of words in it, not two sentences |\n"
    )
    code, out = run("prose_check.py", [str(judgement)])
    ok &= check(
        "P2 fires on a chained sentence, not on an aside or a table row",
        code == 1 and out.count("P2") == 1, out,
    )

    result = hook("prose_check.py", {"tool_name": "Edit", "tool_input": {
        "file_path": str(judgement),
        "new_string": "Init the driver before the measurement task starts and nothing else runs; "
                      "otherwise the first conversion returns stale data.\n"}})
    ok &= check("P2 never interrupts an edit, only P1 does", result[0] == 0, result[1])

    odd = tmp / "2026-01-01: draft.md"
    odd.write_text("A clean line.\n")
    code, out = run("prose_check.py", [str(odd)])
    ok &= check("a colon in the path does not crash the check", code == 0, out)
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

    # A vendored tree carries its own ignore file, which is what comment_lint already honours.
    (repo / "src" / "thing" / ".jitter-lint-ignore").write_text("mod.rs\n")
    code, out = run("layout_check.py", [], cwd=repo)
    ok &= check("layout_check walks up to a nested .jitter-lint-ignore", code == 0, out)
    (repo / "src" / "thing" / ".jitter-lint-ignore").unlink()
    return ok


GUARD_PUSHES = [
    ("git push origin main", "a plain push"),
    ("git status && \\\n git push origin main", "a push after a line continuation"),
    ("git commit -m 'fix Bob'\\''s typo'\ngit push origin main", "an apostrophe does not hide the next push"),
    ("echo it's fine; git push origin main", "an unbalanced quote does not hide a push"),
    ('echo "a \\" b"; git push origin main', "an escaped quote does not hide a push"),
    ("bash -c 'cd /repo && git push origin main'", "an operator inside bash -c"),
    ('cat <<< "note"\ngit push origin main', "a here-string does not blind the guard"),
    ("mask=$((1 << bits))\ngit push origin main", "a left shift does not blind the guard"),
    ("git --no-pager push origin main", "a valueless git flag"),
    ("timeout 60 git push origin main", "a wrapper's own arguments"),
    ("sudo git push origin main", "sudo"),
    ("echo main | xargs git push origin", "xargs"),
    ("(git push origin main)", "a subshell"),
    ("if true; then git push origin main; fi", "a then branch"),
    ("for x in a; do git push origin main; done", "a loop body"),
    ("echo $(git push origin main)", "command substitution"),
    ("/usr/bin/git push origin main", "an absolute path"),
    ("git -C /repo push origin main", "git -C"),
    ("git send-email --to a@b patches/", "git send-email, the fourth table row"),
    ("gh release create v1.0", "gh release create, the third table row"),
    ("eval \"git push origin main\"", "eval runs a string"),
    ("env GIT_TRACE=1 git push origin main", "env passes through to the real command"),
    ("sleep 1 & git push origin main", "a background separator still starts a command"),
    ("sudo -u git git push origin main", "an option value is not the program"),
    ("sudo --user=git git push origin main", "an inline option value is not the program"),
    ("sudo env timeout 60 nice git push origin main", "a stack of wrappers"),
    ("gh pr create --fill", "gh pr create"),
    ("cargo publish --dry-run && git push origin main", "a dry run elsewhere does not excuse it"),
    ("gh pr merge 12 --squash", "gh pr merge"),
    ("echo main | xargs git push origin", "xargs fills in a target the guard cannot read"),
]

GUARD_ORDINARY = [
    ("git push --help", "asking for help"),
    ("git push -n origin main", "the short form of --dry-run"),
    ("sudo -u deploy cargo build", "a wrapper running something else entirely"),
    ("git push --dry-run origin main", "a dry run"),
    ("git push -u origin feature-x", "a feature branch by name"),
    ("grep -rn git push docs/", "an unquoted grep"),
    ('git commit -m "wip"   # then git push later', "a trailing comment"),
    ("cat <<'EOF' > doc.md\ngit push origin main\nEOF", "a heredoc body holding a real push"),
    ("cat <<EOF 2>/dev/null\ngit push origin main\nEOF", "a heredoc opener with a redirect"),
    ("tee f <<EOF 1>/dev/null\ngit push origin main\nEOF", "a heredoc opener before a redirect"),
    ('timeout 60 echo "git push"', "a wrapper running something else"),
    ("echo 'careful; git push origin main'", "a separator inside quotes"),
    ("git commit -m 'x' && git status", "local git work"),
    ("git pull --rebase", "a pull"),
    ("gh pr list", "listing PRs"),
    ("sed -i 's/git push/x/' doc.md", "rewriting the words in a file"),
    ("timeout 300 cargo test --features test --locked", "an ordinary wrapped command"),
]


def asks(output):
    return '"permissionDecision": "ask"' in output


def branch_cases(tmp, ok):
    """Feature branches push freely. Master, main, rewrites, deletes and tags ask."""
    tmp = tmp / "branches"
    repo, remote = tmp / "repo", tmp / "remote.git"
    tmp.mkdir()
    git(["init", "-q", "--bare", str(remote)], tmp)
    git(["init", "-q", "-b", "master", str(repo)], tmp)
    git(["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "one"], repo)
    git(["remote", "add", "origin", str(remote)], repo)
    git(["push", "-q", "origin", "master"], repo)

    def push(command, cwd=repo):
        done = subprocess.run(
            [sys.executable, str(TOOLS / "guard_push.py"), "--hook"],
            input=json.dumps({"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": command}}),
            capture_output=True, text=True, check=False,
        )
        return done.returncode == 0 and asks(done.stdout)

    ok &= check("a bare push on master asks", push("git push"))
    ok &= check("HEAD on master asks", push("git push -u origin HEAD"))
    git(["switch", "-q", "-c", "feature"], repo)
    for command in ("git push", "git push -u origin HEAD", "git push origin feature", "git push origin feature:feature"):
        ok &= check("a feature branch pushes freely: " + command, not push(command))
    ok &= check("git -C reads the branch of that repo", not push("git -C {} push".format(repo), cwd=tmp))
    for command, name in [
        ("git push -f origin feature", "--force"),
        ("git push --force-with-lease=feature origin feature", "--force-with-lease=..."),
        ("git push origin +feature", "a + refspec"),
        ("git push origin :feature", "a : refspec"),
        ("git push --delete origin feature", "--delete"),
        ("git push origin HEAD:main", "HEAD onto main"),
        ("git push origin refs/heads/master", "a full ref to master"),
        ("git push --tags", "--tags"),
        ("git push --mirror origin", "--mirror"),
    ]:
        ok &= check("a feature branch still asks for " + name, push(command))
    git(["tag", "v1"], repo)
    ok &= check("a tag by name asks", push("git push origin v1"))
    git(["branch", "-q", "-u", "origin/master"], repo)
    ok &= check("a branch whose upstream is master asks", push("git push"))
    git(["switch", "-q", "--detach"], repo)
    ok &= check("a detached HEAD asks", push("git push"))
    return ok


def guard_cases(ok):
    for command, name in GUARD_PUSHES:
        result = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": command}})
        ok &= check("guard asks: " + name, result[0] == 0 and asks(result[1]), result[1])
    for command, name in GUARD_ORDINARY:
        result = hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": command}})
        ok &= check("guard allows: " + name, result[0] == 0 and not asks(result[1]), result[1])

    # The threshold is a setting, not a rule, so both directions have to work.
    # The candidate expansion used to be quadratic, which cost seconds on an ordinary command.
    long_command = "timeout 300 cargo test " + " ".join("--arg{}".format(i) for i in range(800))
    started = time.time()
    hook("guard_push.py", {"tool_name": "Bash", "tool_input": {"command": long_command}})
    elapsed = time.time() - started
    ok &= check("guard stays fast on a long command", elapsed < 1.0, "{:.2f}s".format(elapsed))
    return ok


def typst_package_cases(ok):
    """The session hook links whatever version directories exist, so the layout has to hold."""
    root = TOOLS.parent
    versions = sorted((root / "typst").glob("*/*/lib.typ"))
    ok &= check("the typst package has a lib.typ where the hook expects one", bool(versions),
                "expected typst/<package>/<version>/lib.typ")
    for entry in versions:
        manifest = entry.parent / "typst.toml"
        ok &= check(
            "{} ships a manifest naming its entrypoint".format(entry.parent.name),
            manifest.is_file() and 'entrypoint = "lib.typ"' in manifest.read_text(),
            str(manifest),
        )
    return ok


def hook_wiring_cases(ok):
    """The session hooks must not interpolate a missing plugin root into the session."""
    wiring = json.loads((TOOLS.parent / "hooks" / "hooks.json").read_text())
    commands = " ".join(
        entry["command"]
        for event in wiring["hooks"].values()
        for matcher in event
        for entry in matcher["hooks"]
    )
    # The versioned cache path goes stale on a plugin update, so the skill must not write it.
    extras = (TOOLS.parent / "skills" / "setup-extras" / "SKILL.md").read_text()
    ok &= check(
        "setup-extras warns against writing the versioned plugin path",
        "plugins/cache" in extras and "marketplaces" in extras,
        "it should prefer the marketplace checkout or a clone",
    )

    marker = "jitter-ai-agent/onboarded"
    skill = (TOOLS.parent / "skills" / "setup-extras" / "SKILL.md").read_text()
    ok &= check(
        "the first-run prompt and the skill agree on the marker path",
        marker in commands and marker in skill,
        "hook and skill must write and read the same file",
    )
    unguarded = [
        entry["command"]
        for event in wiring["hooks"].values()
        for matcher in event
        for entry in matcher["hooks"]
        if "CLAUDE_PLUGIN_ROOT" in entry["command"]
        and '[ -n "${CLAUDE_PLUGIN_ROOT}" ]' not in entry["command"]
    ]
    ok &= check("every session hook guards against a missing plugin root", not unguarded, "\n".join(unguarded))
    return ok


def knowledge_session_cases(tmp, ok):
    """The hook prompts once, stays quiet after a no, and pulls only a clean clone on a new session."""
    tmp = tmp / "knowledge"
    tmp.mkdir()
    env = dict(os.environ, XDG_CONFIG_HOME=str(tmp / "cfg"), XDG_CACHE_HOME=str(tmp / "cache"))

    def session(source):
        done = subprocess.run(
            [sys.executable, str(TOOLS / "knowledge_session.py")], input=json.dumps({"source": source}),
            capture_output=True, text=True, env=env, check=False,
        )
        return done.returncode, done.stdout

    rc, out = session("startup")
    ok &= check("knowledge hook offers setup when nothing is configured", rc == 0 and "setup-extras" in out, out)
    (tmp / "cache" / "jitter-ai-agent").mkdir(parents=True)
    (tmp / "cache" / "jitter-ai-agent" / "knowledge-declined").write_text("x")
    rc, out = session("startup")
    ok &= check("knowledge hook is silent after a no", rc == 0 and not out.strip(), out)

    config = tmp / "cfg" / "jitter-knowledge" / "path"
    config.parent.mkdir(parents=True)
    config.write_text(str(tmp / "nowhere") + "\n")
    rc, out = session("startup")
    ok &= check("knowledge hook flags a path without a clone", rc == 0 and "no knowledge base clone" in out, out)

    upstream, clone = tmp / "upstream", tmp / "clone"
    git(["init", "-q", "-b", "master", str(upstream)], tmp)
    (upstream / "knowledge").mkdir()
    (upstream / "knowledge" / "index.md").write_text("one\n")
    for args in (["add", "."], ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "one"]):
        git(args, upstream)
    git(["clone", "-q", str(upstream), str(clone)], tmp)
    config.write_text(str(clone) + "\n")

    (upstream / "knowledge" / "index.md").write_text("two\n")
    git(["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qam", "two"], upstream)
    rc, out = session("resume")
    pulled = (clone / "knowledge" / "index.md").read_text() == "two\n"
    ok &= check("knowledge hook does not pull on resume", "JITTER_KNOWLEDGE=" in out and not pulled, out)
    rc, out = session("startup")
    pulled = (clone / "knowledge" / "index.md").read_text() == "two\n"
    ok &= check("knowledge hook pulls a clean clone on startup", pulled and "Not updated" not in out, out)

    (clone / "knowledge" / "draft.md").write_text("wip\n")
    rc, out = session("startup")
    ok &= check("knowledge hook leaves a dirty clone alone", rc == 0 and "uncommitted changes" in out, out)
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
        ok = branch_cases(tmp, ok)
        ok = knowledge_session_cases(tmp, ok)
    ok = hook_wiring_cases(ok)
    ok = typst_package_cases(ok)
    print("\n{}".format("all good" if ok else "something regressed"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
