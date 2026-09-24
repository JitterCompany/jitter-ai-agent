---
name: setup-repo
description: Wire a Jitter repo into the shared agent conventions - the plugin via .claude/settings.json, the clippy workspace lints, rustfmt, and the path-leak pre-commit check. Use when asked to set up the shared rules, the house lints or the agent conventions in a repo, or when a repo has none of them yet.
---

# Set a repo up for the shared conventions

Templates live in `${CLAUDE_PLUGIN_ROOT}/templates/`. Read each one before copying, and merge rather than overwrite when the target file exists.

## 1. Plugin, so colleagues get the rules automatically

Merge `templates/claude-settings.json` into the repo's `.claude/settings.json` and commit it. Anyone who opens the repo is then prompted to install the marketplace and the plugin. A repo with KiCad files also gets `rules/hardware.md` automatically, nothing to add.

## 2. Clippy lints

Merge `templates/workspace-lints.toml` into the workspace `Cargo.toml`, and add `lints.workspace = true` to each member crate. Start at `warn`.

Run `cargo clippy --all-targets` once and report the count. Do not fix the whole backlog unless asked. When a repo is clean, propose `-D warnings` in its CI workflow.

## 3. rustfmt

If the repo has no `rustfmt.toml`, copy `templates/rustfmt.toml`. Formatting is `cargo +nightly fmt --all`.

## 4. Path leak check

Offer to install `tools/path_leak_check.py --staged` as a pre-commit hook. It blocks `/home/<user>`, personal email addresses, keys and tokens from entering a commit.

In a KiCad repo, add `tools/kicad_project_check.py` to the same hook, so a `.kicad_pro` that lost its ERC/DRC exclusions cannot be committed by accident. Mention the `fix-kicad-paths` skill for the absolute paths KiCad bakes into project files.

## 5. Vendored code

If the repo vendors third-party or generated Rust, add a `.jitter-lint-ignore` at the repo root with one glob per line, so the comment check skips it.

## Verify

- `python3 tools/comment_lint.py $(git ls-files '*.rs') | wc -l`, then report the number and the worst offenders.
- `cargo +nightly fmt --all --check`.
- Confirm the settings file parses: `python3 -m json.tool .claude/settings.json`.
