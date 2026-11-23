cmake_minimum_required(VERSION 3.13)

# Waveshare RP2350-Zero (LED: GPIO16 の WS2812。単色 LED は無し)
set(PICO_BOARD waveshare_rp2350_zero CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform")

include(pico_sdk_import.cmake)

project(rp2350_zero_blink C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

add_executable(rp2350_zero_blink main.c)
pico_generate_pio_header(rp2350_zero_blink ${CMAKE_CURRENT_LIST_DIR}/ws2812.pio)
target_link_libraries(rp2350_zero_blink pico_stdlib hardware_pio)

# USB シリアルを有効化 → 1200bps タッチ / Reset インターフェースで書き込みモードに入れる
pico_enable_stdio_usb(rp2350_zero_blink 1)
pico_enable_stdio_uart(rp2350_zero_blink 0)

pico_add_extra_outputs(rp2350_zero_blink)
