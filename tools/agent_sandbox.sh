#!/bin/sh
# Run a headless Claude Code session that cannot touch the real user's plugin state.
#   tools/agent_sandbox.sh [claude args...]      e.g. tools/agent_sandbox.sh -p "What now?" --plugin-dir .
# Markers, the knowledge base path, the checks path and global git config go to a throwaway
# directory, so a scripted "yes, set it up" in a test writes nothing a person relies on.
# Login stays in ~/.claude, so no new sign-in is needed.
set -eu

# GIT_CONFIG_GLOBAL needs git 2.32. Older git ignores it and the test would write the real config.
git_version=$(git --version | sed 's/[^0-9.]*\([0-9]*\)\.\([0-9]*\).*/\1 \2/')
set -- $git_version "$@"
if [ "$1" -lt 2 ] || { [ "$1" -eq 2 ] && [ "$2" -lt 32 ]; }; then
  echo "agent_sandbox.sh needs git 2.32 or newer to isolate the global git config, found $(git --version)" >&2
  exit 1
fi
shift 2

SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/agent-sandbox.XXXXXX")
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/cache" "$SANDBOX/config" "$SANDBOX/data"
touch "$SANDBOX/gitconfig"

XDG_CACHE_HOME="$SANDBOX/cache" XDG_CONFIG_HOME="$SANDBOX/config" XDG_DATA_HOME="$SANDBOX/data" \
GIT_CONFIG_GLOBAL="$SANDBOX/gitconfig" \
  claude "$@"
