// Waveshare RP2350-Zero: オンボード WS2812 (GPIO16) で Lチカ
// 赤 → 緑 → 青 を点滅。USB シリアルに状態を出力。
#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "ws2812.pio.h"

#ifndef PICO_DEFAULT_WS2812_PIN
#define PICO_DEFAULT_WS2812_PIN 16
#endif

#define BRIGHTNESS 32   // 0-255 (眩しいので控えめ)

static PIO pio = pio0;
static uint sm = 0;

static void put_rgb(uint8_t r, uint8_t g, uint8_t b) {
    // WS2812 は GRB 順・MSB ファースト (24bit を上位に詰める)
    uint32_t grb = ((uint32_t)g << 16) | ((uint32_t)r << 8) | b;
    pio_sm_put_blocking(pio, sm, grb << 8u);
}

int main(void) {
    stdio_init_all();

    uint offset = pio_add_program(pio, &ws2812_program);
    ws2812_program_init(pio, sm, offset, PICO_DEFAULT_WS2812_PIN, 800000);

    static const struct { uint8_t r, g, b; const char *name; } colors[] = {
        { BRIGHTNESS, 0, 0, "red"   },
        { 0, BRIGHTNESS, 0, "green" },
        { 0, 0, BRIGHTNESS, "blue"  },
    };

    for (uint32_t n = 0;; n++) {
        const int i = n % 3;
        put_rgb(colors[i].r, colors[i].g, colors[i].b);
        printf("blink %lu: %s\n", (unsigned long)n, colors[i].name);
        sleep_ms(300);
        put_rgb(0, 0, 0);
        sleep_ms(300);
    }
}
