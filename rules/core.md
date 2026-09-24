# Jitter working rules

Canonical source: `jitter-agent/rules/core.md`. Full Rust guide: `rules/rust-style.md` (skill `rust-style`). Writing: `rules/prose.md`.

## Rust

- Iterators and slices over index loops. Enums and `match` over flag ints and bools. `Option` / `Result` with `?` over sentinel values. Return values, not out-params.
- Comments say why, or state a contract. They never restate the code. No banner lines, no "Step 1:" narration, no change history such as "now uses X instead of Y".
- At most 4 consecutive `//` lines. When you change code, trim the comments around it instead of growing them.
- The why of a design lives in `docs/decisions/`, not inline.
- When refactoring, keep existing comments and `debug!` / `info!` / `warn!` / `error!` / `trace!` statements.
- No macros to reduce repetition. Avoid `matches!()` where `if let`, let-else or `match` reads better.
- A module with submodules is `mything.rs` beside `mything/`, never `mything/mod.rs`. Import types with `use`, not fully-qualified paths.
- Prefer an enum plus an optional free-text note over one free-text field that a tool parses. Derive scope from a property in the data, never from a hardcoded list of names.
- Extend a CLI with an optional new arg instead of replacing the flag set. For new infrastructure, survey established crates before writing a wrapper.
- Baseline: the [rust-analyzer style guide](https://github.com/rust-lang/rust-analyzer/blob/master/docs/dev/style.md).
- Firmware is `no_std`: no `Box`, no `alloc`, use `heapless`.

## Working

- `cargo +nightly fmt --all` before committing.
- Never `git push` or open a PR until that specific push is approved. Committing locally is fine.
- Compact commit messages, few commits, never `git add -A`.
- A branch tracks a remote branch of the same name or nothing at all. Use `--no-track`, or `git push -u origin HEAD`. Check `git status -sb` after branching.
- Account for staged and unstaged changes in a diff. No `cd X && git ...`, use absolute paths.
- Never commit or push from inside a submodule. Check with the user, then work in that library's own source tree on its own branch.
- Say what is verified and what is a hypothesis. Search the repo for the protocol spec or the existing constant before guessing one.
- Refactor from the highest abstraction level down. Keep specifics in the one place that owns them, and point at it from elsewhere.
- Running tools and scripts to find things out is fine, as long as they cannot touch production or the user's running setup. Show the command so it can be repeated by hand.
- Prefer a script file over long inline bash. Avoid `rm -rf` with wildcards, prefer adding a folder over deleting one.
- Keep replies terse. Do not echo a plan back.
- A PR review judges substance. Format and compile checks are CI's job.

## Company

- Public JitterCompany repos never name a customer or a project code. Strip project references from files and commit messages when moving code between repos.
- Placeholder names must be obviously fake. No plausible-looking brands.
- Nothing that leaves the machine carries local paths or personal data. No `/home/<user>`, `/Users/<user>`, usernames, personal email addresses, machine names or API tokens in committed files, generated reports, netlists or docs. Use `${KIPRJMOD}`, `$HOME`, a relative path or a config value. This is privacy and it also stops "works on my machine" artifacts. `tools/path_leak_check.py` checks it.
- Hardware documentation (modules, antennas, RF) lives in the hardware repo, not the firmware repo.
- Writing style, everywhere including comments, docs and commit messages: no em dashes, short sentences, no formal register, bullets or a table over a paragraph.
