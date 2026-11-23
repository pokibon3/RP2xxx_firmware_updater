#!/bin/sh
# macOS 用アプリをビルド → dist/mac/RP2xxx Updater.app と配布用 zip
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pyinstaller
.venv/bin/pyinstaller --noconfirm --distpath dist/mac --workpath build/mac rp2updater.spec
rm -rf "dist/mac/RP2xxx Updater" dist/mac/RP2xxx-Updater-mac.zip   # .app 以外の中間フォルダは不要
ditto -c -k --keepParent "dist/mac/RP2xxx Updater.app" dist/mac/RP2xxx-Updater-mac.zip
echo "→ dist/mac/RP2xxx Updater.app / dist/mac/RP2xxx-Updater-mac.zip"
