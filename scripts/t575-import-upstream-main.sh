#!/usr/bin/env bash
# Import latest upstream Active3 family history into our separate LTE integration branch.
# IMPORTANT: upstream is FETCH-ONLY; no flash, build, commit, push or branch overwrite.
set -euo pipefail

EXPECTED_BRANCH='integration/upstream-active3-family-firstboot'
UPSTREAM_URL='https://github.com/exynos-linux/samsung-gtactive3.git'
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
[ "$(git branch --show-current)" = "$EXPECTED_BRANCH" ] || {
  echo "Refusing: checkout $EXPECTED_BRANCH first." >&2; exit 1;
}
[ -z "$(git status --porcelain)" ] || {
  echo "Refusing: worktree is not clean. Preserve your local changes first." >&2; exit 1;
}
origin="$(git remote get-url origin)"
case "$origin" in
  *Forenzo/samsung-gtactive3LTE* ) ;;
  *) echo "Refusing: origin is not Forenzo/samsung-gtactive3LTE ($origin)." >&2; exit 1;;
esac

# Use a dedicated remote name to avoid modifying any pre-existing 'upstream'.
REMOTE=t575-original-readonly
if git remote get-url "$REMOTE" >/dev/null 2>&1; then
  [ "$(git remote get-url "$REMOTE")" = "$UPSTREAM_URL" ] || {
    echo "Refusing: $REMOTE already points somewhere else." >&2; exit 1;
  }
else
  git remote add "$REMOTE" "$UPSTREAM_URL"
fi

echo "Fetching original author's main branch, read-only..."
git fetch --no-tags "$REMOTE" main
upstream_ref="$REMOTE/main"
upstream_sha="$(git rev-parse "$upstream_ref")"
our_sha="$(git rev-parse HEAD)"
echo "Our branch: $our_sha"
echo "Upstream main: $upstream_sha"

git merge-base HEAD "$upstream_ref" >/dev/null || {
  echo "No common Git ancestor; refusing an unrelated-history merge." >&2; exit 1;
}

echo "Upstream changes vs our fork:"
git diff --stat HEAD "$upstream_ref" | tail -n 32
echo
echo "Performing a NON-COMMITTING integration merge..."
if git merge --no-commit --no-ff "$upstream_ref"; then
  echo "Integration merged into the working tree only."
  echo "Review: git diff --cached --stat; git status"
  echo "No commit or push performed. Keep all LTE safety and boot guards."
else
  echo "Git detected merge conflicts. This is expected for divergent board code."
  echo "Resolve manually, preserving upstream shared infrastructure and our LTE fixes."
  echo "List conflicts: git diff --name-only --diff-filter=U"
  echo "Abort safely: git merge --abort"
  exit 2
fi
