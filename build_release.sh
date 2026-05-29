#!/usr/bin/env bash
# build_release.sh — Package audio_transcriber into a distributable ZIP.
#
# Reads version from pyproject.toml, stages files in /tmp, excludes dev cruft,
# and writes dist/audio_transcriber-latest.zip. Run from the project root or
# anywhere — paths are resolved relative to this script's directory.

set -euo pipefail

# Resolve the project root as the directory containing this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# --- 1. Read version from pyproject.toml -----------------------------------
PYPROJECT="$PROJECT_ROOT/pyproject.toml"
if [[ ! -f "$PYPROJECT" ]]; then
    echo "ERROR: pyproject.toml not found at $PYPROJECT" >&2
    exit 1
fi

# Match the first `version = "X.Y.Z"` line at top-of-line (project version).
VERSION="$(grep -E '^version = "[^"]+"' "$PYPROJECT" | head -n1 | sed -E 's/^version = "([^"]+)"/\1/')"
if [[ -z "$VERSION" ]]; then
    echo "ERROR: could not parse version from $PYPROJECT" >&2
    exit 1
fi
echo "Building audio_transcriber v$VERSION"

# --- 2. Create a clean staging directory -----------------------------------
STAGE_DIR="/tmp/audio_transcriber_release_${VERSION}"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
echo "Staging at: $STAGE_DIR"

# --- 3. Copy required paths into staging -----------------------------------
# Directories copied recursively, files copied as-is. Layout under staging
# mirrors the project root so the ZIP is self-contained.
copy_into_stage() {
    local rel="$1"
    local src="$PROJECT_ROOT/$rel"
    local dest="$STAGE_DIR/$rel"
    if [[ ! -e "$src" ]]; then
        echo "WARNING: missing source $src — skipping" >&2
        return
    fi
    mkdir -p "$(dirname "$dest")"
    cp -R "$src" "$dest"
}

copy_into_stage "audio_transcriber"
copy_into_stage "installer/install.ps1"
copy_into_stage "installer/update_check.ps1"
copy_into_stage "installer/uninstall.ps1"
copy_into_stage "installer/bootstrap.ps1"
copy_into_stage "config"
copy_into_stage "pyproject.toml"
copy_into_stage "README.md"
copy_into_stage "docs/CEO_HANDOFF.md"
copy_into_stage "docs/CLIENT_INSTALL.md"

# --- 4. Prune excluded paths from staging ----------------------------------
# Remove dev/runtime artifacts that should never ship to clients.
echo "Pruning excluded paths..."
find "$STAGE_DIR" \
    \( -type d \( \
        -name ".venv" -o \
        -name ".pytest_cache" -o \
        -name "tests" -o \
        -name "__pycache__" -o \
        -name ".git" -o \
        -name ".claude" -o \
        -name "dist" \
    \) \) -prune -exec rm -rf {} +

find "$STAGE_DIR" \
    \( -type f \( \
        -name "*.pyc" -o \
        -name ".DS_Store" \
    \) \) -delete

# --- 5. Build the ZIP ------------------------------------------------------
DIST_DIR="$PROJECT_ROOT/dist"
mkdir -p "$DIST_DIR"
ZIP_PATH="$DIST_DIR/audio_transcriber-latest.zip"
rm -f "$ZIP_PATH"

# Zip from inside the staging dir so archive paths are relative.
( cd "$STAGE_DIR" && zip -rq "$ZIP_PATH" . )

# --- 6 & 7. Report hash, path, and size ------------------------------------
SHA256="$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')"
# macOS-compatible byte size via stat.
SIZE_BYTES="$(stat -f%z "$ZIP_PATH")"
# Human-readable size (KB/MB).
SIZE_HUMAN="$(ls -lh "$ZIP_PATH" | awk '{print $5}')"

echo
echo "=========================================="
echo " Build complete"
echo "=========================================="
echo " ZIP:    $ZIP_PATH"
echo " Size:   $SIZE_HUMAN ($SIZE_BYTES bytes)"
echo " SHA256: $SHA256"
echo "=========================================="
