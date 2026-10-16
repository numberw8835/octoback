#!/usr/bin/env bash
# Compiles Octoback into a single executable with Nuitka and installs it to ~/.local/bin
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
VENV_DIR="$BUILD_DIR/venv"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

# Step 1: Check the system tools we cannot install ourselves
for tool in python3 gcc; do
    if ! command -v "$tool" >/dev/null; then
        echo "Error: '$tool' is not installed. Install it with your package manager first."
        exit 1
    fi
done

# Step 2: Build tools live in their own venv so the system Python stays untouched
echo "==> Preparing build environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet --upgrade nuitka pyyaml patchelf zstandard

# Step 3: Compile into one self-contained file (venv first in PATH so Nuitka finds patchelf)
echo "==> Compiling with Nuitka (this takes a few minutes)..."
PATH="$VENV_DIR/bin:$PATH" python -m nuitka \
    --onefile \
    --assume-yes-for-downloads \
    --output-dir="$BUILD_DIR" \
    --output-filename=octoback \
    --remove-output \
    "$PROJECT_DIR/octoback.py"

# Step 4: Install the executable
mkdir -p "$INSTALL_DIR"
install -m 755 "$BUILD_DIR/octoback" "$INSTALL_DIR/octoback"
echo "==> Installed: $INSTALL_DIR/octoback"

# Step 5: Remind the user if the install folder is not in PATH
case ":$PATH:" in
    *":$INSTALL_DIR:"*) echo "==> Done! Run: octoback --help" ;;
    *) echo "==> Done! Add $INSTALL_DIR to your PATH to run 'octoback' from anywhere." ;;
esac
