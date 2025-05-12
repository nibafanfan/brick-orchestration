#!/bin/bash

# This script restores the original README.md from the upstream (biobricks-ai) repository for each repo under brick_repos.
# Usage: Run from the brick_repos directory.

for repo in */; do
  cd "$repo"
  # Add upstream if not present
  if ! git remote | grep -q upstream; then
    git remote add upstream "git@github.com:biobricks-ai/${repo%/}.git"
  fi
  git fetch upstream
  # Checkout the original README.md from upstream/main
  git checkout upstream/main -- README.md
  cd ..
done 