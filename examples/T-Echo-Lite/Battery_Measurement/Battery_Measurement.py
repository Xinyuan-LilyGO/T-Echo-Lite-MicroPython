from machine import Pin
import time
from t_echo_lite_config import *

power_on()
button = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
led = Pin(LED_1, Pin.OUT, value=1)
measurement = Pin(BATTERY_MEASUREMENT_CONTROL, Pin.OUT, value=0)
enabled = False
previous = button.value()
last_press = time.ticks_add(time.ticks_ms(), -200)
next_print = time.ticks_ms()
print("Ciallo")

while True:
    now = time.ticks_ms()
    state = button.value()
    if (previous and not state and
            time.ticks_diff(now, last_press) >= 200):
        enabled = not enabled
        last_press = now
        measurement.value(1 if enabled else 0)
        led.value(0 if enabled else 1)
        next_print = now
    previous = state

    if time.ticks_diff(now, next_print) >= 0:
        raw, adc_voltage, battery_voltage = battery_adc_read()
        print("Turn %s battery voltage measurement" %
              ("on" if enabled else "off"))
        print("ADC Value:%d" % raw)
        print("ADC Voltage: %.3f V" % adc_voltage)
        print("Battery Voltage: %.3f V\n" % battery_voltage)
        next_print = time.ticks_add(now, 3000)

    time.sleep_ms(10)
