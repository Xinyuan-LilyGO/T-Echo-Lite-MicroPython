from machine import Pin
import time
from example_helpers import make_display
from ssd1681 import SSD1681
from t_echo_lite_config import LED_1, LED_2, LED_3, power_on

power_on()
print("Ciallo")
leds = [Pin(pin, Pin.OUT, value=1) for pin in (LED_1, LED_2, LED_3)]
display = make_display()
display.begin()
display.fill(1)
display.show(SSD1681.FULL_REFRESH)
count = 0
screen_partial_refresh_init_lock = False

while True:
    display.fill(1)
    display.freesans9_digits(str(count), 10, 60, 0, size=3)

    if count and count % 10 == 0:
        display.show(SSD1681.FAST_REFRESH)
        screen_partial_refresh_init_lock = False
    else:
        if not screen_partial_refresh_init_lock:
            display.set_ram_value_base_map(SSD1681.FAST_REFRESH)
            screen_partial_refresh_init_lock = True
        display.show(SSD1681.PARTIAL_REFRESH)

    time.sleep(1)
    count += 1
    for led in leds:
        led.value(1 if count % 2 == 0 else 0)
    print("LED ON" if count % 2 == 0 else "LED OFF")
