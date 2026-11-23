cmake_minimum_required(VERSION 3.13)

# WeAct Studio RP2350A Core (4MB/16MB) / RP2350B Core 共通 (LED: GPIO25)
set(PICO_BOARD weact_studio_rp2350a_core_v10_4mb CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform")

include(pico_sdk_import.cmake)

project(weact_rp2350_blink C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

add_executable(weact_rp2350_blink main.c)
target_link_libraries(weact_rp2350_blink pico_stdlib)

# USB シリアルを有効化 → 1200bps タッチ / Reset インターフェースで書き込みモードに入れる
pico_enable_stdio_usb(weact_rp2350_blink 1)
pico_enable_stdio_uart(weact_rp2350_blink 0)

pico_add_extra_outputs(weact_rp2350_blink)
