from machine import Pin
import sys
import time

if "/flash/lib" in sys.path:
    sys.path.remove("/flash/lib")
sys.path.insert(0, "/flash/lib")

from audio_tools import notification
from es8311 import ES8311
from example_helpers import shared_i2c
from t_echo_lite_config import *

print("Ciallo")
power_on(reset=True)
button = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
codec = ES8311(shared_i2c(100000), ES8311_IIC_ADDRESS, ES8311_ADC_DATA,
               ES8311_DAC_DATA, ES8311_WS_LRCK, ES8311_BCLK, ES8311_MCLK)
codec.begin(44100, 191, adc=True)
audio = notification()
play_count = 1

while True:
    if not button.value():
        time.sleep_ms(300)
        for register in range(256):
            try:
                value = codec.read_register(register)
                value_text = "0" if value == 0 else "0X%X" % value
                print("Es8311 register[%d]: %s" % (register, value_text))
            except OSError:
                pass
        play_count += 1
        print("play_count: %u" % play_count)
        print("music play start")
        try:
            codec.play(audio)
            print("music play finish")
        except OSError:
            print("music play fail")
    time.sleep_ms(10)
