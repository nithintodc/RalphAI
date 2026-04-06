#!/usr/bin/env bash
# ── gitpush.sh ── Stage all changes and push to GitHub with a timestamp commit message
set -e

cd "$(dirname "$0")"

git add -A
git commit -m "update $(date '+%Y-%m-%d %H:%M:%S')"
git push -u origin main
