#!/bin/sh
# macOS 用アプリをビルド → dist/RP2xxx Updater.app と配布用 zip
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pyinstaller
.venv/bin/pyinstaller --noconfirm rp2updater.spec
rm -f dist/RP2xxx-Updater-mac.zip
ditto -c -k --keepParent "dist/RP2xxx Updater.app" dist/RP2xxx-Updater-mac.zip
echo "→ dist/RP2xxx Updater.app / dist/RP2xxx-Updater-mac.zip"
