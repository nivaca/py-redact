#!/usr/bin/env bash
# Installs py-redact from this folder of its source, for this user, on Linux
# or macOS, to run with Python (3.14 or later): no binaries are built.
#
#     install/install.sh                    install, or update
#     install/install.sh --python PYTHON    with that Python
#     install/install.sh --uninstall        remove what it installed
#
# It makes a virtual environment of its own and installs py-redact in it,
# with PyMuPDF and PySide6 from PyPI (so it needs internet the first time):
#   Linux:  ~/.local/share/py-redact/venv, a menu entry and its icons;
#   macOS:  ~/Library/Application Support/py-redact/venv, and
#           ~/Applications/py-redact.app, to start it from the Finder,
#           Launchpad or Spotlight.
# On both, the command py-redact is linked in ~/bin, if that folder
# exists, or else in ~/.local/bin. Nothing needs root, and nothing is put
# anywhere else; the settings are never touched.
#
# py-redact: Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
# SPDX-License-Identifier: GPL-3.0-or-later (see LICENSE)

set -euo pipefail

NAME=py-redact
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ROOT=$(dirname -- "$HERE")
ICONS="$ROOT/src/py_redact/icons/linux/hicolor"

usage() {
    sed -n '2,18s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"
}

die() {
    echo "install.sh: $*" >&2
    exit 1
}

say() {
    echo "==> $*"
}

case "$(uname -s)" in
    Linux) SYSTEM=linux ;;
    Darwin) SYSTEM=macos ;;
    *) die "this is for Linux and macOS; on Windows, use install\\install.bat" ;;
esac

if [[ "$SYSTEM" == macos ]]; then
    DATA="$HOME/Library/Application Support/$NAME"
    APP="$HOME/Applications/$NAME.app"
else
    DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$NAME"
    APPLICATIONS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    HICOLOR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
fi
VENV="$DATA/venv"
if [[ -d "$HOME/bin" ]]; then
    BIN="$HOME/bin"
else
    BIN="$HOME/.local/bin"
fi
LINK="$BIN/$NAME"

# ----------------------------------------------------------------- Python

# Is $1 a Python 3.14 or later, with venv and pip?
good_python() {
    "$1" -c 'import sys, venv, ensurepip; sys.exit(sys.version_info < (3, 14))' >/dev/null 2>&1
}

find_python() {
    local candidate
    for candidate in python3.16 python3.15 python3.14 python3 \
        /opt/homebrew/bin/python3 /usr/local/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.1[4-9]/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1 && good_python "$candidate"; then
            command -v "$candidate"
            return
        fi
    done
    return 1
}

no_python() {
    echo "install.sh: py-redact needs Python 3.14 or later, with venv and pip." >&2
    if [[ "$SYSTEM" == macos ]]; then
        echo "  Install it from https://www.python.org/downloads/macos/ or with Homebrew" >&2
        echo "  (brew install python@3.14), and run this again." >&2
    else
        echo "  Install it with the system's packages (Fedora: sudo dnf install python3;" >&2
        echo "  Debian and Ubuntu: sudo apt install python3.14 python3.14-venv, if the" >&2
        echo "  release has it), or with uv (uv python install 3.14), and run this again," >&2
        echo "  giving it with --python if it isn't on the PATH as python3.14." >&2
    fi
    exit 1
}

# ----------------------------------------------------------------- installing

link_command() {
    mkdir -p -- "$BIN"
    if [[ -L "$LINK" ]]; then
        if [[ "$(readlink -- "$LINK")" != "$VENV/bin/$NAME" ]]; then
            echo "  (replacing $LINK, which pointed to $(readlink -- "$LINK"))"
        fi
        ln -sfn -- "$VENV/bin/$NAME" "$LINK"
    elif [[ -e "$LINK" ]]; then
        echo "  $LINK exists and is not a link: it was left as it is." >&2
        return
    else
        ln -s -- "$VENV/bin/$NAME" "$LINK"
    fi
    echo "  the command: $LINK"
    case ":$PATH:" in
        *":$BIN:"*) ;;
        *) echo "  ($BIN is not on your PATH: add it, or run $VENV/bin/$NAME)" ;;
    esac
}

menu_linux() {
    mkdir -p -- "$APPLICATIONS"
    sed -e "s|^Exec=.*|Exec=\"$VENV/bin/$NAME\" %f|" \
        "$ROOT/packaging/$NAME.desktop" >"$APPLICATIONS/$NAME.desktop"
    local folder size
    for folder in "$ICONS"/*/apps; do
        size=$(basename -- "$(dirname -- "$folder")")
        mkdir -p -- "$HICOLOR/$size/apps"
        cp -- "$folder"/$NAME.* "$HICOLOR/$size/apps/"
    done
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database -q "$APPLICATIONS" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 \
        && gtk-update-icon-cache -q -t "$HICOLOR" 2>/dev/null || true
    echo "  the menu entry: $APPLICATIONS/$NAME.desktop"
}

app_macos() {
    local version
    version=$("$VENV/bin/python" -c 'import py_redact; print(py_redact.__version__)')
    rm -rf -- "$APP"
    mkdir -p -- "$APP/Contents/MacOS" "$APP/Contents/Resources"
    # (a script, not a binary: it starts py-redact with the Python of its environment)
    cat >"$APP/Contents/MacOS/$NAME" <<EOF
#!/bin/sh
exec "$VENV/bin/python" -m py_redact.gui "\$@"
EOF
    chmod +x "$APP/Contents/MacOS/$NAME"  # (no --: the chmod of macOS refuses it)
    cat >"$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>$NAME</string>
    <key>CFBundleDisplayName</key><string>$NAME</string>
    <key>CFBundleIdentifier</key><string>io.github.nivaca.py-redact</string>
    <key>CFBundleVersion</key><string>$version</string>
    <key>CFBundleShortVersionString</key><string>$version</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>$NAME</string>
    <key>CFBundleIconFile</key><string>$NAME</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
    if command -v iconutil >/dev/null 2>&1; then
        local set size
        set=$(mktemp -d)/$NAME.iconset
        mkdir -p -- "$set"
        for size in 16 32 128 256 512; do
            cp -- "$ICONS/${size}x${size}/apps/$NAME.png" "$set/icon_${size}x${size}.png"
        done
        cp -- "$ICONS/32x32/apps/$NAME.png" "$set/icon_16x16@2x.png"
        cp -- "$ICONS/64x64/apps/$NAME.png" "$set/icon_32x32@2x.png"
        cp -- "$ICONS/256x256/apps/$NAME.png" "$set/icon_128x128@2x.png"
        cp -- "$ICONS/512x512/apps/$NAME.png" "$set/icon_256x256@2x.png"
        iconutil -c icns -o "$APP/Contents/Resources/$NAME.icns" "$set" || true
        rm -rf -- "$(dirname -- "$set")"
    fi
    touch -- "$APP"  # (so that the Finder shows the new icon)
    echo "  the application: $APP"
}

install() {
    [[ -f "$ROOT/pyproject.toml" && -d "$ROOT/src/py_redact" ]] \
        || die "run it from the folder of py-redact's source (cloned, or the zip unpacked)"
    local python=$1
    if [[ -z "$python" ]]; then
        python=$(find_python) || no_python
    elif ! good_python "$python"; then
        no_python
    fi
    say "Python: $python ($("$python" -c 'import sys; print(sys.version.split()[0])'))"
    say "Making the environment: $VENV"
    mkdir -p -- "$DATA"
    "$python" -m venv --clear "$VENV"
    say "Installing py-redact, PyMuPDF and PySide6 in it (this takes a while the first time)"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet "$ROOT"
    say "Checking that it starts"
    "$VENV/bin/$NAME" --version
    say "Installed:"
    link_command
    if [[ "$SYSTEM" == macos ]]; then
        app_macos
    else
        menu_linux
    fi
    echo
    echo "Run it with: $NAME [file.pdf], or from the menu of applications."
    echo "To update it, run this again after updating the source; to remove it,"
    echo "$0 --uninstall."
}

uninstall() {
    say "Removing py-redact"
    if [[ -L "$LINK" && "$(readlink -- "$LINK")" == "$VENV/bin/$NAME" ]]; then
        rm -f -- "$LINK" && echo "  $LINK"
    fi
    if [[ -d "$VENV" ]]; then
        rm -rf -- "$VENV" && echo "  $VENV"
    fi
    rmdir -- "$DATA" 2>/dev/null || true  # (on macOS, the settings are there too: kept)
    if [[ "$SYSTEM" == macos ]]; then
        if [[ -d "$APP" ]]; then
            rm -rf -- "$APP" && echo "  $APP"
        fi
    else
        # (only the menu entry this made, which runs the program of its environment, and its icons)
        if [[ -f "$APPLICATIONS/$NAME.desktop" ]] && grep -qF "$VENV/bin/$NAME" "$APPLICATIONS/$NAME.desktop"; then
            rm -f -- "$APPLICATIONS/$NAME.desktop" && echo "  $APPLICATIONS/$NAME.desktop"
            rm -f -- "$HICOLOR"/*/apps/$NAME.png "$HICOLOR"/*/apps/$NAME.svg && echo "  its icons"
            command -v update-desktop-database >/dev/null 2>&1 \
                && update-desktop-database -q "$APPLICATIONS" 2>/dev/null || true
        fi
    fi
    echo "The settings and the redaction codes were kept; see the README, \"Settings and files\"."
}

PYTHON=""
ACTION=install
while [[ $# -gt 0 ]]; do
    case "$1" in
        --python) [[ $# -ge 2 ]] || die "--python needs a Python"; PYTHON=$2; shift ;;
        --python=*) PYTHON=${1#--python=} ;;
        --uninstall) ACTION=uninstall ;;
        -h | --help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done

if [[ "$ACTION" == uninstall ]]; then
    uninstall
else
    install "$PYTHON"
fi
