---
name: setup-extras
description: Offer a colleague the optional parts of the Jitter agent setup the first time they use it: the commit-time checks, the shared git hook and a clone of the shared knowledge base. Use when the session says this person has not been offered the extras or has no knowledge base set up, when someone asks how to finish setting this up, or when a commit-time check turns out not to be installed.
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

They catch a local path or personal data in anything about to be committed (C3), and KiCad dropping its own ERC and DRC exclusions (H5). Both see things an edit-time check cannot.

Check what is already there, and only offer what is missing:

```sh
cat ~/.config/jitter-git/checks-path 2>/dev/null
echo "$JITTER_PRECOMMIT_CHECKS"
```

To enable, with their yes, add one line to `~/.config/jitter-git/checks-path`. Use a path that survives a plugin update, in this order:

1. `~/.claude/plugins/marketplaces/jitter/tools/precommit`, the marketplace checkout, which `/plugin marketplace update` keeps current.
2. Their own clone of this repo, if they maintain one, which `git pull` keeps current.

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

If they have no plugin install of their own, point that line at any clone of this repo instead. The checks are plain python and do not need the plugin.

## 2. The shared git hook

The checks above only run if the repo actually calls the shared hook from `JitterCompany/git_utils`. Look first:

```sh
git config --get core.hooksPath
ls -l .git/hooks/pre-commit
```

One of those two should point into a `git_utils` clone. If neither does, the hook is not installed and the checks will never run. Offer the global setting, which covers every repo at once:

```sh
git config --global core.hooksPath /path/to/git_utils/scripts
```

If they have no clone of `git_utils`, say where it is (`github.com/JitterCompany/git_utils`, public) and let them clone it where they keep their tools. Do not clone it into a project repo.

A repo can still add its own `.git-pre-commit`, which the shared hook runs after the rest.

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
