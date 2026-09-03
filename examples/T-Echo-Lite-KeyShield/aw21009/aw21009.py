import time
from aw21009 import AW21009
from example_helpers import shared_i2c
from t_echo_lite_config import AW21009_IIC_ADDRESS, power_on

power_on(reset=True)
led = AW21009(shared_i2c(), AW21009_IIC_ADDRESS)
led.begin()
brightness = 0
step = 20

while True:
    led.brightness(None, brightness)
    brightness += step
    if brightness >= 4095:
        brightness, step = 4095, -20
    elif brightness <= 0:
        brightness, step = 0, 20
    time.sleep_ms(10)

