#!/bin/sh
# PlatformIO 同梱の pico-sdk / toolchain でビルドし、UF2 を生成する
set -e
cd "$(dirname "$0")"
PIO_PKG="$HOME/.platformio/packages"
export PICO_SDK_PATH="${PICO_SDK_PATH:-$PIO_PKG/framework-arduinopico/pico-sdk}"
export PICO_TOOLCHAIN_PATH="${PICO_TOOLCHAIN_PATH:-$PIO_PKG/toolchain-rp2040-earlephilhower/bin}"

# picotool のバージョンが SDK と合わないため picotool 無しでビルドし、UF2 は自前で変換
cmake -S . -B build -G Ninja -DPICO_NO_PICOTOOL=1
ninja -C build
python3 -I ../../tools/bin2uf2.py build/weact_rp2350_blink.bin weact_rp2350_blink.uf2 --family rp2350-arm-s
