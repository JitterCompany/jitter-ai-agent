---
name: style-feedback
description: Turn a correction from the user into a rule in the shared jitter-agent repo, so every colleague's next session gets it. Use when the user says something should be remembered for the team, corrects the house style, or asks to add or change a shared rule or convention.
---

# Promote a correction to the team rules

Use this when a correction is general. Something that is only true for this machine, this checkout or this one project belongs in personal memory or in the repo's own CLAUDE.md instead.

## Steps

1. **Write the rule.** One sentence, imperative, plus the why in a clause. Add a bad-to-good example pair if the rule is about code.
2. **Pick the file** in the `jitter-agent` clone:
   - `rules/core.md` if it is short, universal and worth having in every session. This file is loaded on every session start, so it stays near 40 lines. Adding a line usually means shortening another.
   - `rules/rust-style.md` for Rust detail and examples.
   - `rules/prose.md` for writing style.
   - `rules/hardware.md` for KiCad, PCB and lab rules.
3. **Check for a duplicate** first. Update the existing line rather than adding a near-copy.
4. **Consider a check instead.** If a script can catch it, add it to `tools/comment_lint.py` or `tools/path_leak_check.py`, or as a clippy lint in `templates/workspace-lints.toml`. A check beats a sentence, because it lands in the agent's context exactly when it matters.
5. **Commit on a branch**, one rule per branch, with a commit message that says what changed and why.
6. **Ask before pushing.** Never push or open the PR until the user approves that specific push.

## Finding the clone

The rules loaded in this session live under `${CLAUDE_PLUGIN_ROOT}`, which is the plugin cache when the plugin came from the marketplace. Do not edit that copy, it is overwritten on update. Ask the user where their `jitter-agent` working clone is, or clone it fresh, make the change there, then `/plugin marketplace update jitter` once it is merged.
