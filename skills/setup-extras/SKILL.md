---
name: setup-extras
description: Offer a colleague the optional Jitter setup once: commit-time checks, the shared git hook, a knowledge base clone. Use when the session says the extras were not offered or the knowledge base is missing.
---

# Finish setting someone up

The plugin works with nothing configured. Three extras are worth offering once, and never again.

Ask in one message, listing what each does, and take a no for an answer. Then write the marker either way, so nobody is asked twice. The knowledge base has its own session check and its own marker, so when only that one is missing, offer only section 3.

Write these files with the Write tool rather than a shell redirect. A shell command that touches a dotfile needs its own approval, and in a session that has already said yes to the setup, stopping again to ask for a `>>` is noise. Read an existing file first and add your line to it, never replace it.

- marker: `${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/onboarded`, containing today's date
- checks: `~/.config/jitter-git/checks-path`, one path per line
- knowledge base: `~/.config/jitter-knowledge/path`, one line, the absolute path of the clone
- knowledge base declined: `${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/knowledge-declined`, containing today's date

## 1. The commit-time checks

They catch a local path or personal data in anything about to be committed (C3), KiCad dropping its own ERC and DRC exclusions (H5), and another project's name hidden in KiCad annotation (C1). They see things an edit-time check cannot.

Your own commits need none of this: `guard_commit.py` runs the same checks on every commit you make. The setup below is for the commits people make by hand. Offer it, and do not push it on someone who declines.

Check what is already there, and only offer what is missing:

```sh
cat ~/.config/jitter-git/checks-path 2>/dev/null
echo "$JITTER_PRECOMMIT_CHECKS"
```

To enable, with their yes, add one line to `~/.config/jitter-git/checks-path`. Use a path that survives a plugin update, in this order:

1. `~/.claude/plugins/marketplaces/jitter/tools/precommit`, the marketplace checkout, which `/plugin marketplace update` keeps current. Offer to turn on auto-update for the `jitter` marketplace in `/plugin`.
2. When the agent runs as its own user and the person has no Claude Code: the agent user's marketplace checkout, if their account can read it (a shared group).
3. A clone of this repo that stays on `master` and gets pulled. Not the clone someone develops in: its current branch decides which checks run, so they drift or run half-finished.

Do **not** write the `JITTER_ROOT` from the session header. That is the installed copy for one plugin version, such as `.../plugins/cache/jitter/jitter/0.1.0`, and it stops existing on the next version bump, leaving the checks silently unconfigured.

Keep any lines that are already in there. Use this file, not their shell profile. An IDE or a GUI git client often does not load a profile, and the checks would then be silently off for the person least likely to notice.

Then prove it works rather than assuming it does. In a scratch directory, not one of their repos:

```sh
python3 "$JITTER_ROOT/tools/precommit/path_leak_check.py" --staged
```

### When the agent runs as its own user

On a machine where Claude runs under a sandbox user, `~` is that user's home, not the person's. The config you write then gates the commits **you** make, and theirs still run unchecked, because the hook reads the home of whoever runs `git commit`.

Say so plainly and give them the line for their own terminal:

```sh
mkdir -p ~/.config/jitter-git
echo "$HOME/.claude/plugins/marketplaces/jitter/tools/precommit" >> ~/.config/jitter-git/checks-path
```

If they have no plugin install of their own, use the agent user's marketplace path instead, when their account can read it. Have them run the proof command above from their own account. Otherwise use option 3. The checks are plain python and do not need the plugin.

## 2. The shared git hook

The checks in section 1 only run on a person's own commits if the repo calls the hook from `JitterCompany/git_utils` (public). That is the one thing git itself enforces, so offer it once, as part of the first-run question.

### Look first

```sh
git config --global --get core.hooksPath
git -C ~/git remote get-url origin
```

It is in place when `core.hooksPath` points at the `scripts` folder of a `git_utils` clone, usually `~/git/scripts`. A repo that still has a hook link or copy in `.git/hooks` is fine too, but only that repo is covered.

### Install it the git_utils way

With their yes, and in their own terminal when the agent runs as its own user:

```sh
git clone https://github.com/JitterCompany/git_utils.git ~/git   # skip if a clone exists
git config --global core.hooksPath ~/git/scripts
```

One setting covers every repo, existing and future, and a `git -C ~/git pull` updates them all at once.

`core.hooksPath` makes git ignore each repo's `.git/hooks`. That costs nothing in our setup: a project that needs its own hook commits a `.git-pre-commit` in its root, and the shared hook runs it after the checks. It does switch off hooks that tools install into `.git/hooks`. If `git config --global --get filter.lfs.process` prints something, they use git LFS: tell them its hooks stop running, and let them decide.

If `core.hooksPath` is already set to something else, leave it and ask.

### If they skip it

Do not ask again. Their hand-made commits then go unchecked, but yours do not: `guard_commit.py` runs the section 1 checks on every commit you make, with no setup. Say that in one line, so they know what the no costs.

## Keep it current

A setup someone accepted can quietly stop working. The session check looks for this without touching the network, and reports each problem once:

- **git_utils hook too old to run the shared checks:** `git -C ~/git pull`. Every repo uses the clone's script, so they all pick it up at once. If the hook is a copy in one repo's `.git/hooks` instead, setting `core.hooksPath` as above replaces it.
- **git_utils clone behind its last fetch:** the same pull.
- **checks-path entry gone:** usually a versioned plugin path that an update removed. Replace it with a copy from section 1.
- **checks-path entry on a feature branch:** someone is developing in that clone. Point the line at a copy that stays on `master`, from section 1. Do not switch their branch.

Offer the fix once, and run it in their own terminal when the agent runs as its own user. Then the session check stays quiet until something else changes.

## 3. The shared knowledge base

`JitterCompany/jitter-knowledge` is a private repo with what we know about parts, tools, protocols and customers. The `knowledge` skill reads it and files new entries to it. Each session pulls it, when the clone is clean and on master.

1. **Look for a clone first.** Try `~/dev/jitter/jitter-knowledge`, then the folder that holds their other Jitter repos. Confirm with `git -C <dir> remote get-url origin`.
2. **Otherwise offer to clone it.** Suggest the folder next to their other Jitter repos, and let them pick another:
   ```sh
   git clone git@github.com:JitterCompany/jitter-knowledge.git ~/dev/jitter/jitter-knowledge
   ```
   If that fails on access, they need GitHub access to the repo or an SSH key. Tell them, and stop there. Do not work around it.
3. **Write the path** to `~/.config/jitter-knowledge/path`: one line, absolute. This file stays on their machine, so a home path in it is fine.
4. **Prove it works:** `knowledge/index.md` in the clone has `okf_version` in its frontmatter.

If they say no, write the declined marker, so the session check stays quiet.

When the agent runs as its own user, the same caveat as section 1 holds. Give them the lines for their own terminal:

```sh
git clone git@github.com:JitterCompany/jitter-knowledge.git ~/dev/jitter/jitter-knowledge
mkdir -p ~/.config/jitter-knowledge
echo "$HOME/dev/jitter/jitter-knowledge" > ~/.config/jitter-knowledge/path
```

## What needs no setup

- The rules, the edit-time checks and the push guard come with the plugin.
- The `jitter-report` Typst package is linked at session start. Confirm with `ls ~/.local/share/typst/packages/local/jitter-report` if a report fails to import it.

## If they say no

Write the marker anyway and move on. Mention that `setup-extras` will do it later if they change their mind. Do not raise it again in the same session.
