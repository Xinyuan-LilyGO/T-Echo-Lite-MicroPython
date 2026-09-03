from machine import Pin
import time
from example_helpers import shared_i2c
from t_echo_lite_config import *
from tca8418 import TCA8418

power_on(reset=True)
interrupt = Pin(TCA8418_INT, Pin.IN, Pin.PULL_UP)
keyboard = TCA8418(shared_i2c(), TCA8418_IIC_ADDRESS, TCA8418_MAP)
keyboard.begin(TCA8418_KEYPAD_SCAN_HEIGHT, TCA8418_KEYPAD_SCAN_WIDTH)
print("Tca8418 ready")

while True:
    if not interrupt.value():
        for number, pressed, position, label in keyboard.events():
            print("keypad event: num:%d x:%d y:%d pressed:%d" %
                  (number, position[0], position[1], pressed))
            print("keypad string:", label)
    time.sleep_ms(10)

