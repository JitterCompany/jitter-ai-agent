# Jitter working rules

Canonical source: `jitter-ai-agent/rules/core.md`. Full Rust guide: `rules/rust-style.md` (skill `rust-style`). Writing: `rules/prose.md`. Hardware: `rules/hardware.md`, loaded on its own in KiCad repos.

Ids: `R` rust-style.md, `P` prose.md, `H` hardware.md, `W` `C` `M` here. This digest repeats the short form of a rule under its own id.

## Rust

- **R1** Iterators and slices over index loops. Enums and `match` over flag ints and bools. `Option` / `Result` with `?` over sentinel values. Return values, not out-params.
- **R2** Comments say why, or state a contract. They never restate the code. No banner lines, no "Step 1:" narration, no change history such as "now uses X instead of Y".
- **R3** At most 4 consecutive `//` lines in what you write. Do not grow the comments around code you touch, and leave comments you did not write alone (R5).
- **R4** The why of a design lives in `docs/decisions/`, not inline.
- **R5** When refactoring, keep existing comments and `debug!` / `info!` / `warn!` / `error!` / `trace!` statements.
- **R6** No macros to reduce repetition. Avoid `matches!()` where `if let`, let-else or `match` reads better.
- **R7** A module with submodules is `mything.rs` beside `mything/`, never `mything/mod.rs`. Import types with `use`, not fully-qualified paths.
- **R8** Prefer an enum plus an optional free-text note over one free-text field that a tool parses. Derive scope from a property in the data, never from a hardcoded list of names.
- **R9** Extend a CLI with an optional new arg instead of replacing the flag set. For new infrastructure, survey established crates before writing a wrapper.
- **R10** Baseline: the [rust-analyzer style guide](https://github.com/rust-lang/rust-analyzer/blob/master/docs/dev/style.md).
- **R11** Firmware is `no_std`: no `Box`, no `alloc`, use `heapless`.

## Working

- **W1** `cargo +nightly fmt --all` before committing.
- **W2** Never `git push` or open a PR until that specific push is approved. Committing locally is fine.
- **W3** Compact commit messages, few commits, never `git add -A`.
- **W4** A branch tracks a remote branch of the same name or nothing at all. Use `--no-track`, or `git push -u origin HEAD`. Check `git status -sb` after branching.
- **W5** Account for staged and unstaged changes in a diff. No `cd X && git ...`, use absolute paths.
- **W6** Never commit or push from inside a submodule. Check with the user, then work in that library's own source tree on its own branch.
- **W7** Say what is verified and what is a hypothesis. Search the repo for the protocol spec or the existing constant before guessing one.
- **W8** Refactor from the highest abstraction level down. Keep specifics in the one place that owns them, and point at it from elsewhere.
- **W9** Running tools and scripts to find things out is fine, as long as they cannot touch production or the user's running setup. Show the command so it can be repeated by hand.
- **W10** Prefer a script file over long inline bash. Avoid `rm -rf` with wildcards, prefer adding a folder over deleting one.
- **W11** Keep replies terse. Do not echo a plan back.
- **W12** A PR review judges substance, including style and design. Leave formatting and compile errors to CI.

## Company

- **C1** Public JitterCompany repos never name a customer or a project code. Strip project references from files and commit messages when moving code between repos.
- **C2** Placeholder names must be obviously fake. No plausible-looking brands.
- **C3** Nothing that leaves the machine carries local paths or personal data. No `/home/<user>`, `/Users/<user>`, usernames, personal email addresses, machine names or API tokens in committed files, generated reports, netlists or docs. Use `${KIPRJMOD}`, `$HOME`, a relative path or a config value. This is privacy and it also stops "works on my machine" artifacts. `tools/path_leak_check.py` checks it.
- **C4** Hardware documentation (modules, antennas, RF) lives in the hardware repo, not the firmware repo.
- **P1-P4** Writing style, everywhere including comments, docs and commit messages: no em dashes, short sentences, no formal register, bullets or a table over a paragraph. Full set in `prose.md`.

## Meta

- **M1** These rules come from the private repo `JitterCompany/jitter-ai-agent`. When the user says "remember this across all projects", "new company-wide rule", "add this to the rules" or similar, use the `agent-rules` skill: it writes the rule, branches in a clone of that repo and asks before pushing. Personal memory alone reaches nobody else.
- **M2** Do not narrate rule ids. Cite one only when challenged, or when a rule made you do something other than what the user asked for. Then name it, quote it in one line, and offer the four levels: skip it this once, an exception for this project (its CLAUDE.md), a personal exception (their `~/.claude/CLAUDE.md`), or change it for everybody (a PR on `jitter-ai-agent`). Apply the choice right away.
- **M3** A rule that only holds for one project or one machine does not belong in this file. Project facts go in that repo's CLAUDE.md, personal preferences in personal memory.
