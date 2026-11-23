// WeAct Studio RP2350 Core: オンボード LED (GPIO25) で Lチカ
// USB シリアルに状態を出力。
#include <stdio.h>
#include "pico/stdlib.h"

#ifndef PICO_DEFAULT_LED_PIN
#define PICO_DEFAULT_LED_PIN 25
#endif

int main(void) {
    stdio_init_all();

    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

    for (uint32_t n = 0;; n++) {
        gpio_put(PICO_DEFAULT_LED_PIN, 1);
        printf("blink %lu: on\n", (unsigned long)n);
        sleep_ms(250);
        gpio_put(PICO_DEFAULT_LED_PIN, 0);
        sleep_ms(250);
    }
}
