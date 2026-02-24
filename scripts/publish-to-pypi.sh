#!/usr/bin/env bash
# Build (and optionally upload) all packages to PyPI in dependency order.
# Requires: poetry, twine (for upload). Env: PYPI_USER, PYPI_PASSWORD or token.
#
# Usage:
#   ./scripts/publish-to-pypi.sh              # build only (dist/ in each package)
#   ./scripts/publish-to-pypi.sh --upload      # build + upload to PyPI
#   VERSION=0.2.0 ./scripts/publish-to-pypi.sh --upload

set -e
cd "$(dirname "$0")/.."
VERSION="${VERSION:-}"
if [ -n "$VERSION" ]; then
  PREPARE_EXTRA="--version $VERSION"
else
  PREPARE_EXTRA=""
fi

echo "=== Preparing pyproject.toml for release ==="
python3 scripts/prepare_pypi_release.py $PREPARE_EXTRA

echo ""
echo "=== Building packages ==="
for pkg in basket-ai basket-tui basket-agent basket-trajectory basket-assistant; do
  d=packages/$pkg
  if [ -d "$d" ]; then
    (cd "$d" && poetry build)
  fi
done

if [ "$1" = "--upload" ]; then
  echo ""
  echo "=== Uploading to PyPI ==="
  for pkg in basket-ai basket-tui basket-agent basket-trajectory basket-assistant; do
    d=packages/$pkg
    if [ -d "$d" ]; then
      (cd "$d" && twine upload dist/*)
    fi
  done
fi

echo ""
echo "=== Restoring pyproject.toml ==="
python3 scripts/prepare_pypi_release.py --restore

echo "Done."
