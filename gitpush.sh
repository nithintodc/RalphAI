#!/bin/bash
git add .
git commit -m "chore: automated commit"
BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed "s@^refs/remotes/origin/@@")
if [ -z "$BRANCH" ]; then BRANCH="main"; fi
git push origin $BRANCH
