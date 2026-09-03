from machine import Pin
import time
from button import Button
from example_helpers import make_display
from ssd1681 import SSD1681
from t_echo_lite_config import nRF52840_BOOT, power_on

power_on()
print("Ciallo")
display = make_display()
display.begin()
button = Button(Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP))
names = {Button.SINGLE_CLICK: "1.SINGLE_CLICK",
         Button.DOUBLE_CLICK: "2.DOUBLE_CLICK",
         Button.LONG_PRESS: "3.LONG_PRESS"}
serial_names = {Button.SINGLE_CLICK: "SINGLE_CLICK",
                Button.DOUBLE_CLICK: "DOUBLE_CLICK",
                Button.LONG_PRESS: "LONG_PRESS"}


def show_message(message, mode):
    display.fill(1)
    display.gfx_text(message, 10, 60, 0, size=2, wrap=True)
    display.show(mode)


show_message("Please press the button", SSD1681.FULL_REFRESH)

while True:
    gesture = button.wait_gesture()
    if gesture:
        print("Key triggered: " + serial_names[gesture])
        show_message(names[gesture], SSD1681.FAST_REFRESH)
    time.sleep_ms(10)
