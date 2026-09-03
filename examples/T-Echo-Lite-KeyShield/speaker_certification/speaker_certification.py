import time
from machine import Pin
from audio_tools import tone
from es8311 import ES8311
from example_helpers import shared_i2c
from t_echo_lite_config import *

print("Speaker certification: 1 kHz square wave")
power_on(reset=True)
stop_button = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
codec = ES8311(shared_i2c(), ES8311_IIC_ADDRESS, ES8311_ADC_DATA,
               ES8311_DAC_DATA, ES8311_WS_LRCK, ES8311_BCLK, ES8311_MCLK)
codec.begin(44100, 175, adc=False)
wave = tone(1000, 44100, 10, 1000, square=True)
started = False

try:
    codec.i2s.start(wave)
    started = True
    print("Square wave output started: 1000 Hz, 44.1 kHz, 16-bit")

    while True:
        if not stop_button.value():
            time.sleep_ms(30)
            if not stop_button.value():
                break
        if codec.i2s.needs_buffer():
            codec.i2s.queue(wave)
        # Always yield so USB Ctrl+C/IDE Stop is serviced promptly.
        time.sleep_ms(1)
except KeyboardInterrupt:
    pass
finally:
    if started:
        codec.i2s.stop()
    codec.set_dac_volume(0)
    print("Square wave output stopped")
