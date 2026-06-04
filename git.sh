#!/usr/bin/env bash
#
# Global git.sh for RalphAI
# Usage: ./git.sh ["Commit message"]
#
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

REMOTE_NAME="origin"
REMOTE_URL="https://github.com/nithintodc/RalphAI.git"
MSG="${1:-Update RalphAI agents and core}"

if git remote get-url "$REMOTE_NAME" &>/dev/null; then
  current_url="$(git remote get-url "$REMOTE_NAME")"
  if [ "$current_url" != "$REMOTE_URL" ]; then
    echo "Updating $REMOTE_NAME remote: $current_url -> $REMOTE_URL"
    git remote set-url "$REMOTE_NAME" "$REMOTE_URL"
  fi
else
  echo "Adding $REMOTE_NAME remote -> $REMOTE_URL"
  git remote add "$REMOTE_NAME" "$REMOTE_URL"
fi

echo "Adding all changes..."
git add .

echo "Committing with message: $MSG"
git commit -m "$MSG" || echo "No changes to commit."

BRANCH="$(git branch --show-current)"
if [ -z "$BRANCH" ]; then
  BRANCH="main"
fi

echo "Pushing $BRANCH to $REMOTE_URL..."
git push -u "$REMOTE_NAME" "$BRANCH"

echo "Done!"
