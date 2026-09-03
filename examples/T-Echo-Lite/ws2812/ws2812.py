import time
from t_echo_lite_config import (EXT_1x4P_1_IO_0_23,
                                EXT_1x4P_1_IO_0_25,
                                power_on, spi_bus)
from ws2812 import WS2812

NUM_LEDS = 10
power_on()
print("Ciallo")
# MISO is unused by the LEDs; the same exposed pin is only a harmless placeholder.
spi = spi_bus(2, EXT_1x4P_1_IO_0_25, EXT_1x4P_1_IO_0_23,
              EXT_1x4P_1_IO_0_25, 3200000)
leds = WS2812(spi, NUM_LEDS, brightness=100)

for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255),
              (255, 255, 255), (0, 0, 0)):
    leds.fill(color)
    leds.show()
    time.sleep_ms(500)

while True:
    for first_hue in range(0, 5 * 65536, 256):
        for index in range(NUM_LEDS):
            leds.set(index, *leds.hsv(first_hue + index * 65536 // NUM_LEDS))
        leds.show()
        time.sleep_ms(100)
