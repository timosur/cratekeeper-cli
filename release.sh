#!/usr/bin/env bash
# Release helper — bumps version in pyproject.toml, commits, tags, and pushes.
#
# Usage:
#   ./release.sh <version>     # e.g. ./release.sh 1.2.0
#   ./release.sh patch         # 1.0.0 → 1.0.1
#   ./release.sh minor         # 1.0.0 → 1.1.0
#   ./release.sh major         # 1.0.0 → 2.0.0
set -euo pipefail

PYPROJECT="pyproject.toml"

# ── Helpers ──────────────────────────────────────────────────────────

die()  { echo "ERROR: $1" >&2; exit 1; }

current_version() {
    grep -m1 '^version' "$PYPROJECT" | sed 's/.*"\(.*\)"/\1/'
}

bump() {
    local cur="$1" part="$2"
    IFS='.' read -r major minor patch <<< "$cur"
    case "$part" in
        major) echo "$((major + 1)).0.0" ;;
        minor) echo "$major.$((minor + 1)).0" ;;
        patch) echo "$major.$minor.$((patch + 1))" ;;
        *)     die "Unknown bump type: $part" ;;
    esac
}

# ── Preconditions ────────────────────────────────────────────────────

[[ $# -eq 1 ]] || die "Usage: ./release.sh <version|major|minor|patch>"

# Must be on main
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[[ "$BRANCH" == "main" ]] || die "Must be on main branch (currently on $BRANCH)"

# Working tree must be clean (staged or unstaged changes)
git diff --quiet && git diff --cached --quiet \
    || die "Working tree is dirty. Commit or stash changes first."

# ── Resolve version ──────────────────────────────────────────────────

OLD_VERSION=$(current_version)
ARG="$1"

case "$ARG" in
    major|minor|patch) NEW_VERSION=$(bump "$OLD_VERSION" "$ARG") ;;
    [0-9]*)            NEW_VERSION="$ARG" ;;
    *)                 die "Invalid argument: $ARG (expected version or major|minor|patch)" ;;
esac

# Validate semver format
[[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || die "Version must be semver (got: $NEW_VERSION)"

TAG="v$NEW_VERSION"

# Tag must not already exist
git tag -l "$TAG" | grep -q . && die "Tag $TAG already exists"

echo "  $OLD_VERSION → $NEW_VERSION"
echo ""

# ── Bump, commit, tag, push ─────────────────────────────────────────

# Update pyproject.toml
sed -i '' "s/^version = \"$OLD_VERSION\"/version = \"$NEW_VERSION\"/" "$PYPROJECT"

git add "$PYPROJECT"
git commit -m "release: v$NEW_VERSION"
git tag "$TAG"
git push origin main --tags

echo ""
echo "Done. GitHub Actions will create the release at:"
echo "  https://github.com/timosur/cratekeeper-cli/releases/tag/$TAG"
