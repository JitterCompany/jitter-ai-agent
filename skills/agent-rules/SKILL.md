---
name: agent-rules
description: Add, change or override a shared Jitter rule in the jitter-ai-agent repo, so every colleague's next session gets it. Use when the user says "remember this across all projects", "new company-wide rule", "add this to the house rules", when they correct the house style or conventions, or when they want an exception to a rule that just shaped your behaviour.
---

# Change the shared rules

The rules loaded in this session come from `JitterCompany/jitter-ai-agent`. This skill covers two cases: adding a rule, and overriding one.

## A. New or changed rule

1. **Check the scope.** Company-wide goes in this repo. One project goes in that repo's `CLAUDE.md`. One machine or one person's taste goes in their personal memory or `~/.claude/CLAUDE.md`. Ask which of the three when it is not obvious. A fact rather than a way of working, such as a chip erratum or a customer's setup, belongs in the knowledge base: use the `knowledge` skill.
2. **Write it.** One imperative sentence with the why in a clause. Add a bad-to-good pair when it is about code. Give it the next free id in its section (R, W, C in `core.md`).
3. **Pick the file:**
   - `rules/core.md` if it is short, universal and worth loading into every session. This file is injected at every session start, so it stays near 45 lines. Adding a line usually means shortening another.
   - `rules/rust-style.md` for Rust detail and examples.
   - `rules/prose.md` for writing style.
   - `rules/hardware.md` for KiCad, PCB and lab.
   - A new `skills/<name>/SKILL.md` when it is a procedure an agent carries out, for example a repeatable task with steps and verification. A procedure only people follow goes in the knowledge base instead, through the `knowledge` skill.
4. **Check for a duplicate.** Grep the repo and update the existing line instead of adding a near-copy.
5. **Prefer a check over a sentence.** If a script can catch it, add it to `tools/comment_lint.py`, `tools/path_leak_check.py`, `tools/kicad_project_check.py`, or as a clippy lint in `templates/workspace-lints.toml`. A check lands in context exactly when it matters and never gets summarized away. Tune it against a real repo and report the hit count before committing it.
6. **Bump the plugin version** in `.claude-plugin/plugin.json` and `marketplace.json`, or the change never reaches anyone's cached copy.
7. **Branch and commit.** One rule per branch, named `rule/<short-slug>`. The commit message says what the rule is and why it exists.
8. **Run `python3 tools/ci_local.py`** and fix what fails. It runs the same steps as CI.
9. **Push the branch and open the PR.** Opening it brings up an approval prompt (W2). Give the user the link.

## B. Override a rule

When a rule caused something the user did not want, name the id, quote it in one line, then offer:

| Level | Where it goes |
|---|---|
| Just this once | Nothing written. Do it their way now. |
| This project | An exception in the repo's `CLAUDE.md`, naming the rule id and the reason. |
| Just me | Their `~/.claude/CLAUDE.md` or personal memory, naming the rule id. |
| Everybody | Edit or delete the rule in `jitter-ai-agent`, branch and PR as in part A. |

Apply the choice to the work in front of you straight away, do not only record it.

## Finding the clone

`$JITTER_ROOT` is the plugin cache when the plugin came from the marketplace, and it is overwritten on update. Never edit there. Ask the user where their `jitter-ai-agent` working clone is, or clone it fresh, edit there, and run `/plugin marketplace update jitter` once the change is merged.
