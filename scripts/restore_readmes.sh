#!/usr/bin/env bash
set -euo pipefail
TARGET_DATE="2025-05-10 23:59:59"
BRICKS_DIR="$(pwd)/brick_repos"
DEFAULT_MAIN="main"

for repo_path in "$BRICKS_DIR"/*; do
  [[ -d "$repo_path/.git" ]] || continue
  pushd "$repo_path" >/dev/null

  branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "$DEFAULT_MAIN")

  # Check if repo is shallow; if yes, unshallow it
  if [[ -f .git/shallow ]]; then
    echo "🔄 Unshallowing $(basename "$repo_path")..."
    git fetch --unshallow
  else
    git fetch
  fi

  commit=$(git rev-list -1 --before="$TARGET_DATE" "$branch" || true)

  if [[ -z "$commit" ]]; then
    echo "⚠️  $(basename "$repo_path"): No commit before $TARGET_DATE — skipped."
    popd >/dev/null; continue
  fi

  git checkout "$commit" -- README.md

  if git diff --quiet README.md; then
    echo "ℹ️  $(basename "$repo_path"): README already matches target state."
    popd >/dev/null; continue
  fi

  git commit -m "docs: restore README to state from $(date -j -f '%Y-%m-%d %H:%M:%S' "$TARGET_DATE" '+%F')" README.md

  if git push; then
    echo "✅  $(basename "$repo_path"): pushed directly to origin."
  else
    fork_url="https://github.com/nibafanfan/$(basename "$repo_path").git"
    git remote add nibafanfan "$fork_url" 2>/dev/null || true
    new_branch="restore-readme-$(date +%Y%m%d%H%M%S)"
    git checkout -b "$new_branch"
    git push -u nibafanfan "$new_branch" && \
      echo "➡️  $(basename "$repo_path"): Open PR at https://github.com/biobricks-ai/$(basename "$repo_path")"
  fi

  popd >/dev/null
done

echo "✅ Bulk README restore completed."
