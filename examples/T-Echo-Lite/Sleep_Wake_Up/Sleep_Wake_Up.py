from machine import Pin, sleep
import time
from button import Button
from example_helpers import make_display, make_flash, make_radio, setup_gps, shared_i2c
from gfx_resources import FREESANS9PT7B, MATERIAL_MONOCHROME_192X176, ORG_01
from icm20948 import ICM20948
from ssd1681 import SSD1681
from t_echo_lite_config import ICM20948_ADDRESS, nRF52840_BOOT, power_on, system_off_on_button

AUTOMATICALLY_ENTER_LIGHT_SLEEP_TIME = 5000
power_on()
print("Ciallo")

display = make_display()
display.begin()
button_pin = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
button = Button(button_pin)
wake = False
light_sleeping = False


def draw(text, x, y, font=FREESANS9PT7B, size=1, color=0):
    return display.gfx_font_text(text, x, y, font, color, size)


def show_message(text, mode, second_text=None):
    display.fill(1)
    draw(text, 10, 60)
    if second_text is not None:
        draw(second_text, 10, 100)
    display.show(mode)


def flash_device_name(flash):
    return "ZD25Q32D" if flash and flash.jedec_id() == 0xBA4016 else "ZD25WQ32C"


def show_sleep_hardware(flash):
    display.fill(1)
    display.draw_bitmap(0, 0, MATERIAL_MONOCHROME_192X176, 192, 176, 0)
    draw("MCU: nRF52840", 25, 90, ORG_01, color=1)
    draw("Screen: GDEM0122T61", 25, 100, ORG_01, color=1)
    draw("LoRa: SX1262", 25, 110, ORG_01, color=1)
    draw("Flash: " + flash_device_name(flash) + "(4MB)",
         25, 120, ORG_01, color=1)
    draw("Light sleep on", 25, 145, FREESANS9PT7B, color=1)
    display.show(SSD1681.FULL_REFRESH)


print("[SX1262] Initializing ... ")
radio = None
try:
    radio = make_radio(434.0, 125.0, 9, 7, 0x12, 10, 8, True)
    print("SX1262 initialization successful")
except OSError:
    print("SX1262 initialization failed")
    time.sleep_ms(1000)

flash = None
try:
    flash = make_flash()
except OSError:
    print("Flash initialization failed")
    time.sleep_ms(1000)
print("Flash initialization successful")
if flash:
    print("Flash JEDEC ID: 0x%X" % flash.jedec_id())

gps_uart = setup_gps()
imu = None
try:
    imu = ICM20948(shared_i2c(), ICM20948_ADDRESS)
    imu.begin()
    print("ICM20948 initialization successful")
except OSError:
    imu = None
    print("ICM20948 initialization failed")
    time.sleep_ms(1000)


def set_imu_sleep(enabled):
    global imu
    if imu is None:
        return
    try:
        imu.sleep(enabled)
    except OSError:
        # Arduino's IMU sleep call does not abort the whole example when the
        # device is absent or loses power; stop using it for this run.
        imu = None


show_message("Sleep_Wake_Up test", SSD1681.FULL_REFRESH)
wake_deadline = time.ticks_add(time.ticks_ms(),
                               AUTOMATICALLY_ENTER_LIGHT_SLEEP_TIME)


def on_button(pin):
    global wake
    if light_sleeping:
        wake = True


button_pin.irq(trigger=Pin.IRQ_FALLING, handler=on_button)

while True:
    now = time.ticks_ms()
    if not light_sleeping and time.ticks_diff(now, wake_deadline) > 0:
        print("Light Sleep")
        show_message("Light Sleep", SSD1681.FAST_REFRESH)
        show_sleep_hardware(flash)
        light_sleeping = True
        wake = False
        if radio:
            radio.sleep()
        if flash:
            flash.sleep()
        set_imu_sleep(True)

    if light_sleeping:
        while not wake:
            sleep()
            time.sleep_ms(1000)
        if radio:
            radio.standby()
        if flash:
            flash.wake()
        set_imu_sleep(False)
        print("Awakening")
        show_message("Awakening", SSD1681.FULL_REFRESH)
        light_sleeping = False
        wake = False
        wake_deadline = time.ticks_add(time.ticks_ms(),
                                       AUTOMATICALLY_ENTER_LIGHT_SLEEP_TIME)
        continue

    gesture = button.wait_gesture()
    if gesture == Button.SINGLE_CLICK:
        print("Key triggered: SINGLE_CLICK")
        show_message("1.SINGLE_CLICK", SSD1681.FAST_REFRESH)
        wake_deadline = time.ticks_add(time.ticks_ms(),
                                       AUTOMATICALLY_ENTER_LIGHT_SLEEP_TIME)
    elif gesture == Button.DOUBLE_CLICK:
        print("Key triggered: DOUBLE_CLICK")
        show_message("2.DOUBLE_CLICK", SSD1681.FAST_REFRESH)
        wake_deadline = time.ticks_add(time.ticks_ms(),
                                       AUTOMATICALLY_ENTER_LIGHT_SLEEP_TIME)
    elif gesture == Button.LONG_PRESS:
        print("Key triggered: LONG_PRESS")
        show_message("3.LONG_PRESS", SSD1681.FAST_REFRESH, "Deep Sleep")
        if radio:
            radio.sleep()
        if flash:
            flash.sleep()
        set_imu_sleep(True)
        system_off_on_button()
    time.sleep_ms(1)
