from machine import Pin, sleep
import time
from ble_uart import BleUart, BleUnavailable
from button import Button
from example_helpers import make_display, make_flash, make_radio, setup_gps, shared_i2c
from gfx_resources import (FREEMONO9PT7B, FREEMONOBOLD9PT7B,
                           FREESANS9PT7B, MATERIAL_MONOCHROME_192X176, ORG_01)
from icm20948 import ICM20948
from nmea import NMEA
from ssd1681 import SSD1681
from t_echo_lite_config import *

SOFTWARE_NAME = "Original_Test"
SOFTWARE_LASTEDITTIME = "202608181739"
BOARD_VERSION = "V1.0"
AUTO_SLEEP_MS = 5000

power_on()
print("Ciallo")
print("[T-Echo-Lite_%s][%s]_firmware_%s" %
      (BOARD_VERSION, SOFTWARE_NAME, SOFTWARE_LASTEDITTIME))

display = make_display()
display.begin()
button_pin = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
button = Button(button_pin)
leds = [Pin(pin, Pin.OUT, value=1) for pin in (LED_1, LED_2, LED_3)]
identity = unique_device_id()
local_mac = (int.from_bytes(identity[0:4], "big"),
             int.from_bytes(identity[4:8], "big"))
flash = radio = imu = ble = gps_uart = None
gps = NMEA()
battery_enabled = False
ble_received_data = b""
ble_central_name = "Central"
ble_connection_refresh = False
ble_data_refresh = False
ble_next_send = 0
radio_peer = [0, 0]
radio_send = 0
radio_receive = 0
radio_rssi = 0.0
radio_snr = 0.0
radio_state = 0
radio_send_at = 0


def draw(text, x, y, font=ORG_01, size=1, color=0):
    return display.gfx_font_text(text, x, y, font, color, size)


def show_background(light_sleep=False):
    display.fill(1)
    display.draw_bitmap(0, 0, MATERIAL_MONOCHROME_192X176, 192, 176, 0)
    lines = (("MCU: nRF52840", 90), ("Screen: GDEM0122T61", 100),
             ("LoRa: SX1262", 110),
             ("Flash: %s(4MB)" % flash_name(), 120),
             ("GPS: L76K", 130), ("IMU: ICM20948", 140),
             ("Software: " + SOFTWARE_NAME, 150),
             ("LastEditTime: " + SOFTWARE_LASTEDITTIME, 160))
    for text, y in lines:
        draw(text, 25, y, ORG_01, color=1)
    display.show(SSD1681.FULL_REFRESH)


def flash_name():
    return "ZD25Q32D" if flash and flash.jedec_id() == 0xBA4016 else "ZD25WQ32C"


def gfx_test(text):
    display.fill(1)
    draw("TEST", SCREEN_WIDTH // 4 + 5, SCREEN_HEIGHT // 4 - 15,
         FREESANS9PT7B, 2)
    draw(text, 20, SCREEN_HEIGHT // 4 + 10, FREEMONO9PT7B)
    draw("3", SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.FULL_REFRESH)
    display.fill_rect(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 20, 30, 40, 1)
    draw("2", SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.FULL_REFRESH)
    display.fill_rect(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 20, 30, 30, 1)
    draw("1", SCREEN_WIDTH // 2 + 3, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.FULL_REFRESH)


def show_center(text, mode, size=2):
    display.fill(1)
    draw(text, SCREEN_WIDTH // 4 + 5, SCREEN_HEIGHT // 2 - 15,
         FREESANS9PT7B, size)
    display.show(mode)


def show_title(title, x):
    display.fill(1)
    draw(title, x, 15, FREEMONOBOLD9PT7B)


def show_radio():
    show_title("SX1262 Info", 35)
    draw("[Local MAC 0]: %u" % local_mac[0], 20, 70)
    draw("[Local MAC 1]: %u" % local_mac[1], 20, 77)
    draw("<------------Send Info------------> ", 10, 119)
    draw("<-----------Receive Info-----------> ", 9, 140)
    if radio:
        draw("[Status]: Init successful", 20, 28)
        draw("[Mode]: LoRa", 20, 35)
        draw("[Frequency]: 920.0 MHz", 20, 42)
        draw("[Bandwidth]: 125.0 KHz", 20, 49)
        draw("[Output Power]: 22 dBm", 20, 56)
    else:
        draw("[Status]: Init failed", 20, 28)
    update_radio_screen(False)
    display.show(SSD1681.FULL_REFRESH)


def update_radio_screen(refresh=True):
    display.fill_rect(0, 86, SCREEN_HEIGHT, 21, 1)
    if radio_state == 2:
        draw("[Connect]: Connected", 20, 91)
        draw("[Connecting MAC 0]: %u" % radio_peer[0], 20, 98)
        draw("[Connecting MAC 1]: %u" % radio_peer[1], 20, 105)
        display.fill_rect(0, 121, SCREEN_HEIGHT, 7, 1)
        draw("[Send Data]: %u" % radio_send, 20, 126)
        display.fill_rect(0, 142, SCREEN_HEIGHT, 21, 1)
        draw("[Receive Data]: %u" % radio_receive, 20, 147)
        draw("[Receive RSSI]: %.1f dBm" % radio_rssi, 20, 154)
        draw("[Receive SNR]: %.1f dB" % radio_snr, 20, 161)
    elif radio_state == 1:
        draw("[Connect]: Connecting", 20, 91)
        display.fill_rect(0, 121, SCREEN_HEIGHT, 7, 1)
        draw("[Send Data]: %u" % radio_send, 20, 126)
        display.fill_rect(0, 142, SCREEN_HEIGHT, 7, 1)
        draw("[Receive Data]: null", 20, 147)
    else:
        draw("[Connect]: Unconnected", 20, 91)
        draw("[Send Data]: null", 20, 126)
        draw("[Receive Data]: null", 20, 147)
    if refresh:
        display.show(SSD1681.FAST_REFRESH)


def show_battery():
    show_title("Battery Info", 30)
    update_battery()


def update_battery():
    raw, adc_voltage, battery_voltage = battery_read(disable_after=not battery_enabled)
    print("Battery measurement switch " + ("ON" if battery_enabled else "OFF"))
    display.fill_rect(0, 23, SCREEN_WIDTH, 40, 1)
    draw("[Status]: Battery switch " + ("ON" if battery_enabled else "OFF"), 10, 28)
    draw("[ADC Value]: %u%s" % (raw, "" if battery_enabled else " V"), 10, 42)
    draw("[ADC Voltage]: %.03f V" % adc_voltage, 10, 49)
    draw("[Battery Voltage]: %.03f V" % battery_voltage, 10, 56)
    display.show(SSD1681.FAST_REFRESH)


def show_ble():
    show_title("BLE Uart Info", 25)
    draw("<-----------Receive Info-----------> ", 10, 105)
    if ble:
        draw("[Status]: Init successful", 10, 28)
        draw("[BLE Name]: T-Echo-Lite-nRF52840", 10, 35)
        draw("[Uart Serivce]: 6E400001......", 10, 49)
        draw("[Uart RX]: 6E400002......", 10, 56)
        draw("[Uart TX]: 6E400003......", 10, 63)
        draw("[Local MAC]: " + identity.hex().upper(), 10, 77)
    else:
        draw("[Status]: Init failed", 10, 28)
    update_ble_screen(False)
    display.show(SSD1681.FULL_REFRESH)


def update_ble_screen(refresh=True):
    display.fill_rect(0, 86, SCREEN_HEIGHT, 14, 1)
    connected = bool(ble and ble.connected)
    draw("[Connect]: " + ("Connected" if connected else "Unconnected"), 10, 91)
    display.fill_rect(0, 107, SCREEN_HEIGHT, 42, 1)
    if connected:
        draw("[Receive Data]: ", 10, 112)
        text = "".join(chr(value) for value in ble_received_data)
        draw("[%s]-> %s" % (ble_central_name, text), 20, 119)
    else:
        draw("[Receive Data]: null", 10, 112)
    if refresh:
        display.show(SSD1681.FAST_REFRESH)


def show_flash():
    show_title("Flash Info", 45)
    if flash:
        draw("[Status]: Init successful", 10, 28)
        draw("[Name]: " + flash_name(), 10, 42)
        draw("[Size]: 4 MiB", 10, 49)
        draw("[Manufacturer ID]: 0xBA", 10, 56)
    else:
        draw("[Status]: initialization failed", 10, 28)
    display.show(SSD1681.FULL_REFRESH)


def show_gps(waiting=True):
    show_title("GPS Info", 50)
    if waiting:
        draw("[Status]: Waiting for connection......", 10, 28)
    else:
        draw("[Status]: Initialization Successful", 10, 28)
        if gps.valid:
            draw("[Coordinate]: ", 10, 42)
            draw("LNG: %f " % gps.longitude, 20, 49)
            draw("LAT: %f" % gps.latitude, 20, 56)
        else:
            draw("[Coordinate]: Waiting to obtain......", 10, 42)
        draw("[Data]: Waiting to obtain......", 10, 70)
        draw("[Time]: Waiting to obtain......", 10, 77)
    display.show(SSD1681.FAST_REFRESH)


def show_imu():
    show_title("ICM20948 Info", 20)
    display.fill_rect(0, 23, SCREEN_WIDTH, 40, 1)
    if imu:
        print("ICM20948 Initialization Successful")
        pitch, roll, yaw, accel, gyro, mag, temperature = imu.orientation()
        draw("[Status]: Initialization Successful", 10, 28)
        print("Pitch: %.6f" % pitch, end="")
        draw("[Pitch]: %.6f" % pitch, 10, 42)
        print("Roll: %.6f" % roll, end="")
        draw("[Roll]: %.6f" % roll, 10, 49)
        print("Yaw: %.6f" % yaw, end="")
        draw("[Yaw]: %.6f" % yaw, 10, 56)
    else:
        print("ICM20948 initialization failed")
        draw("[Status]: Initialization failed", 10, 28)
    display.show(SSD1681.FAST_REFRESH)


def ble_received(data):
    global ble_received_data, ble_data_refresh
    ble_received_data = data
    print("[%s]-> " % ble_central_name, end="")
    try:
        print(data.decode(), end="")
    except Exception:
        print(repr(data), end="")
    ble_data_refresh = True


def ble_connected(handle):
    global ble_connection_refresh, ble_next_send
    print("Connected to " + ble_central_name)
    ble_connection_refresh = True
    ble_next_send = time.ticks_ms()


def ble_disconnected(handle, reason):
    global ble_connection_refresh, ble_data_refresh
    print("\nDisconnected, reason = 0x%X" % reason)
    ble_connection_refresh = True
    ble_data_refresh = True


def init_stage(stage):
    global radio, flash, gps_uart, imu, ble
    labels = ("SX1262 callback distance test",
              "Solar charging, battery testing and inspection",
              "E-Ink screen test", "LED test", "BLE Uart test",
              "Flash test", "GPS test", "ICM20948 test")
    gfx_test(labels[stage])
    if stage == 0:
        try:
            radio = make_radio(920.0, 125.0, 12, 8, 0xAB, 22, 16, False)
            radio.start_receive()
            print("SX1262 initialization successful")
        except OSError as error:
            radio = None
            print("SX1262 initialization failed")
            print("Error code: %s" % error)
        show_radio()
    elif stage == 1:
        show_battery()
    elif stage == 2:
        display.fill(0)
        display.show(SSD1681.FULL_REFRESH)
        time.sleep_ms(2000)
        display.fill(1)
        display.show(SSD1681.FULL_REFRESH)
        time.sleep_ms(2000)
        show_center("Finish", SSD1681.FAST_REFRESH)
    elif stage == 3:
        show_center("Start", SSD1681.FULL_REFRESH)
        for _ in range(3):
            for led in leds:
                led.value(0)
            time.sleep_ms(1000)
            for led in leds:
                led.value(1)
            time.sleep_ms(1000)
        show_center("Finish", SSD1681.FAST_REFRESH)
    elif stage == 4:
        if ble is None:
            try:
                ble = BleUart(on_receive=ble_received, on_connect=ble_connected,
                              on_disconnect=ble_disconnected)
                ble.start()
                print("BLE initialization successful")
                print("Please use the BLE debugging tool to connect to the development board.")
                print("Once connected, enter character(s) that you wish to send")
            except BleUnavailable:
                ble = None
                print("BLE initialization failed")
        show_ble()
    elif stage == 5:
        try:
            flash = make_flash()
            print("Flash initialization successful")
            print("Flash JEDEC ID: 0x%X" % flash.jedec_id())
        except OSError:
            flash = None
            print("Flash initialization failed")
        show_flash()
    elif stage == 6:
        gps_uart = setup_gps()
        show_gps()
    else:
        try:
            imu = ICM20948(shared_i2c(), ICM20948_ADDRESS)
            imu.begin()
            print("ICM20948 initialization successful")
        except OSError:
            imu = None
            print("ICM20948 initialization failed")
        show_imu()


display.fill(1)
display.show(SSD1681.FULL_REFRESH)
show_background()
time.sleep_ms(3000)

stage = 0
init_stage(stage)
periodic_at = time.ticks_add(time.ticks_ms(), 5000)
while stage < 8:
    now = time.ticks_ms()
    if stage == 0 and radio and radio.poll():
        packet = radio.read()
        if packet and len(packet) == 16 and packet[:4] == b"MAC:":
            incoming_0 = int.from_bytes(packet[8:12], "big")
            incoming_1 = int.from_bytes(packet[4:8], "big")
            if incoming_0 != local_mac[0] and incoming_1 != local_mac[1]:
                radio_peer[:] = (incoming_0, incoming_1)
                radio_receive = int.from_bytes(packet[12:16], "big")
                radio_send = (radio_receive + 1) & 0xFFFFFFFF
                radio_rssi, radio_snr = radio.last_rssi, radio.last_snr
                radio_state = 2
                print("[SX1262] Received packet")
                for index, value in enumerate(packet):
                    print("[SX1262] Data[%d]: 0X%X" % (index, value))
                print("[SX1262] RSSI: %.1f dBm" % radio_rssi)
                print("[SX1262] SNR: %.1f dB" % radio_snr, end="")
                update_radio_screen()
        radio.start_receive()
    elif stage == 1 and time.ticks_diff(now, periodic_at) > 0:
        update_battery()
        periodic_at = time.ticks_add(now, 5000)
    elif stage == 4 and ble:
        if ble_connection_refresh:
            update_ble_screen()
            ble_connection_refresh = False
        if ble_data_refresh:
            update_ble_screen()
            ble_data_refresh = False
        if ble.connected and time.ticks_diff(now, ble_next_send) >= 0:
            ble.write("BLE Test \n[T-Echo-Lite MAC ID]: %s\n[MCU Running time]: %u s\n" %
                      (identity.hex().upper(), now // 1000))
            ble_next_send = time.ticks_add(now, 1000)
    elif stage == 6 and gps_uart:
        data = gps_uart.read()
        if data:
            print("Serial2.available successfully")
            gps.feed(data)
            print("GPS Initialization Successful")
            show_gps(False)
    elif stage == 7 and time.ticks_diff(now, periodic_at) > 0:
        show_imu()
        periodic_at = time.ticks_add(now, 5000)

    gesture = button.wait_gesture()
    if gesture:
        gesture_name = {Button.SINGLE_CLICK: "SINGLE_CLICK",
                        Button.DOUBLE_CLICK: "DOUBLE_CLICK",
                        Button.LONG_PRESS: "LONG_PRESS"}[gesture]
        print("Key triggered: " + gesture_name)
        if gesture == Button.DOUBLE_CLICK:
            init_stage(stage)
        elif gesture == Button.LONG_PRESS:
            if stage == 0 and radio:
                radio.sleep()
            if stage == 7 and imu:
                imu.sleep(True)
            stage += 1
            if stage < 8:
                init_stage(stage)
                periodic_at = time.ticks_add(time.ticks_ms(), 5000)
        elif stage == 0 and radio:
            radio_state = 1
            update_radio_screen()
            packet = b"MAC:" + identity[4:8] + identity[0:4] + radio_send.to_bytes(4, "big")
            print("[SX1262] Sending another packet ... ")
            radio.transmit(packet)
            radio.start_receive()
        elif stage == 1:
            battery_enabled = not battery_enabled
            update_battery()
    time.sleep_ms(1)

for led in leds:
    led.value(0)
display.fill(1)
draw("Sleep_Wake_Up test", 10, 60, FREESANS9PT7B)
display.show(SSD1681.FULL_REFRESH)
wake = False
sleeping = False
wake_deadline = time.ticks_add(time.ticks_ms(), AUTO_SLEEP_MS)


def wake_irq(pin):
    global wake
    if sleeping:
        wake = True


button_pin.irq(trigger=Pin.IRQ_FALLING, handler=wake_irq)
while True:
    if not sleeping and time.ticks_diff(time.ticks_ms(), wake_deadline) > 0:
        print("Light Sleep")
        display.fill(1)
        draw("Light Sleep", 10, 60, FREESANS9PT7B)
        display.show(SSD1681.FAST_REFRESH)
        show_background(True)
        sleeping = True
        wake = False
    if sleeping:
        while not wake:
            sleep()
            time.sleep_ms(1000)
        print("Awakening")
        display.fill(1)
        draw("Awakening", 10, 60, FREESANS9PT7B)
        display.show(SSD1681.FULL_REFRESH)
        sleeping = False
        wake = False
        wake_deadline = time.ticks_add(time.ticks_ms(), AUTO_SLEEP_MS)
        continue
    gesture = button.wait_gesture()
    if gesture:
        name = {Button.SINGLE_CLICK: "SINGLE_CLICK",
                Button.DOUBLE_CLICK: "DOUBLE_CLICK",
                Button.LONG_PRESS: "LONG_PRESS"}[gesture]
        print("Key triggered: " + name)
        display.fill(1)
        draw({Button.SINGLE_CLICK: "1.SINGLE_CLICK",
              Button.DOUBLE_CLICK: "2.DOUBLE_CLICK",
              Button.LONG_PRESS: "3.LONG_PRESS"}[gesture], 10, 60,
             FREESANS9PT7B)
        if gesture == Button.LONG_PRESS:
            draw("Deep Sleep", 10, 100, FREESANS9PT7B)
        display.show(SSD1681.FAST_REFRESH)
        if gesture == Button.LONG_PRESS:
            system_off_on_button()
        wake_deadline = time.ticks_add(time.ticks_ms(), AUTO_SLEEP_MS)
    time.sleep_ms(1)
