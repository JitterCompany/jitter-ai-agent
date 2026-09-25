---
name: adopt-rules
description: Wire a Jitter repo into the shared agent conventions - the plugin via .claude/settings.json, the clippy workspace lints, rustfmt, and the path-leak pre-commit check. Use when asked to set up the shared rules, the house lints or the agent conventions in a repo, or when a repo has none of them yet.
---

# Set a repo up for the shared conventions

Templates live in `$JITTER_ROOT/templates/`. Read each one before copying, and merge rather than overwrite when the target file exists.

## 1. Nothing about the plugin goes in the repo

Do not add `.claude/settings.json`, and do not reference this repo from a project repo at all. Several Jitter repos are public or shared with a client. Colleagues install the plugin once at user level, which is in the README, and the rules then load everywhere.

If someone wants the rules enabled per project rather than globally, that goes in their own untracked `.claude/settings.local.json`.

## 2. Clippy lints

Merge `templates/workspace-lints.toml` into the workspace `Cargo.toml`, and add `lints.workspace = true` to each member crate. Start at `warn`.

Run `cargo clippy --all-targets` once and report the count. Do not fix the whole backlog unless asked. When a repo is clean, propose `-D warnings` in its CI workflow.

## 3. rustfmt

If the repo has no `rustfmt.toml`, copy `templates/rustfmt.toml`. Formatting is `cargo +nightly fmt --all`.

## 4. Pre-commit checks

The repo already has a pre-commit hook if `.git/hooks/pre-commit` points at the shared one from `git_utils`. Check that first, and do not install a second hook beside it.

The plug-in point is `$JITTER_PRECOMMIT_CHECKS` in the user's shell profile, pointing at this repo's `tools/`. Tell them the line to add rather than editing their profile yourself. In a KiCad repo, mention the `fix-kicad-paths` skill for the absolute paths KiCad bakes into project files.

## 5. Vendored code

If the repo vendors third-party or generated Rust, add a `.jitter-lint-ignore` at the repo root with one glob per line, so the comment check skips it.

## Verify

- `python3 tools/comment_lint.py $(git ls-files '*.rs') | wc -l`, then report the number and the worst offenders.
- `cargo +nightly fmt --all --check`.
- Confirm the settings file parses: `python3 -m json.tool .claude/settings.json`.

The plugin writes its own path to `${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/root` at session start, which is what the `JITTER_ROOT=` line above reads. The same path is printed in the session header.
