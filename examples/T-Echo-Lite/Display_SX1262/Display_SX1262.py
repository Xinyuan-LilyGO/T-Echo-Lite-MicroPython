from machine import Pin
import time
from example_helpers import make_display, make_radio
from gfx_resources import FREEMONO9PT7B, FREEMONOBOLD9PT7B, FREESANS9PT7B, ORG_01
from ssd1681 import SSD1681
from t_echo_lite_config import (LED_1, LED_2, SCREEN_HEIGHT, SCREEN_WIDTH,
                                nRF52840_BOOT, power_on, unique_device_id)

UNCONNECTED = 0
CONNECTED = 1
CONNECTING = 2
FREQUENCY = 868.1
BANDWIDTH = 125.0
SPREADING_FACTOR = 12
CODING_RATE = 8
SYNC_WORD = 0xAB
OUTPUT_POWER = 22
PREAMBLE_LENGTH = 16

power_on()
display = make_display()
display.begin()
button = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
led_send = Pin(LED_1, Pin.OUT, value=1)
led_receive = Pin(LED_2, Pin.OUT, value=1)

identity = unique_device_id()
local_mac = (int.from_bytes(identity[0:4], "big"),
             int.from_bytes(identity[4:8], "big"))
peer_mac = [0, 0]
send_data = 0
receive_data = 0
receive_rssi = 0.0
receive_snr = 0.0
connection_state = UNCONNECTED
send_flag = False
refresh_flag = False
error_count = 11
send_at = 0
watchdog_at = 0
send_led_off_at = 0
receive_led_off_at = 0


def draw(text, x, y, font=ORG_01, size=1, color=0):
    return display.gfx_font_text(text, x, y, font, color, size)


def gfx_print_test(text):
    display.fill(1)
    draw("TEST", SCREEN_WIDTH // 4 + 5, SCREEN_HEIGHT // 4 - 15,
         FREESANS9PT7B, 2)
    draw(text, 20, SCREEN_HEIGHT // 4 + 10, FREEMONO9PT7B)
    draw("3", SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.FULL_REFRESH)

    display.fill_rect(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 20,
                      30, 40, 1)
    draw("2", SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.PARTIAL_REFRESH)
    display.show(SSD1681.PARTIAL_REFRESH)

    display.fill_rect(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 20,
                      30, 30, 1)
    draw("1", SCREEN_WIDTH // 2 + 3, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.PARTIAL_REFRESH)
    display.show(SSD1681.PARTIAL_REFRESH)


def gfx_print_sx1262_info():
    display.fill(1)
    draw("SX1262 Info", 35, 15, FREEMONOBOLD9PT7B)
    draw("[Local MAC 0]: %u" % local_mac[0], 20, 70)
    draw("[Local MAC 1]: %u" % local_mac[1], 20, 77)
    draw("<------------Send Info------------> ", 10, 119)
    draw("<-----------Receive Info-----------> ", 9, 140)


def gfx_print_init(success):
    display.fill_rect(0, 23, SCREEN_WIDTH, 40, 1)
    if success:
        draw("[Status]: Init successful", 20, 28)
        draw("[Mode]: LoRa", 20, 35)
        draw("[Frequency]: %.1f MHz" % FREQUENCY, 20, 42)
        draw("[Bandwidth]: %.1f KHz" % BANDWIDTH, 20, 49)
        draw("[Output Power]: %d dBm" % OUTPUT_POWER, 20, 56)
    else:
        draw("[Status]: Init failed", 20, 28)


def gfx_print_transmission():
    display.fill_rect(0, 86, SCREEN_HEIGHT, 21, 1)
    if connection_state == CONNECTED:
        draw("[Connect]: Connected", 20, 91)
        draw("[Connecting MAC 0]: %u" % peer_mac[0], 20, 98)
        draw("[Connecting MAC 1]: %u" % peer_mac[1], 20, 105)
        display.fill_rect(0, 121, SCREEN_HEIGHT, 7, 1)
        draw("[Send Data]: %u" % send_data, 20, 126)
        display.fill_rect(0, 142, SCREEN_HEIGHT, 21, 1)
        draw("[Receive Data]: %u" % receive_data, 20, 147)
        draw("[Receive RSSI]: %.1f dBm" % receive_rssi, 20, 154)
        draw("[Receive SNR]: %.1f dB" % receive_snr, 20, 161)
    elif connection_state == CONNECTING:
        draw("[Connect]: Connecting", 20, 91)
        display.fill_rect(0, 121, SCREEN_HEIGHT, 7, 1)
        draw("[Send Data]: %u" % send_data, 20, 126)
        display.fill_rect(0, 142, SCREEN_HEIGHT, 7, 1)
        draw("[Receive Data]: null", 20, 147)
    else:
        draw("[Connect]: Unconnected", 20, 91)
        display.fill_rect(0, 121, SCREEN_HEIGHT, 7, 1)
        draw("[Send Data]: null", 20, 126)
        display.fill_rect(0, 142, SCREEN_HEIGHT, 21, 1)
        draw("[Receive Data]: null", 20, 147)


def make_packet(value):
    return (b"MAC:" + identity[4:8] + identity[0:4] +
            (value & 0xFFFFFFFF).to_bytes(4, "big"))


print("Ciallo")
gfx_print_test("SX1262 callback distance test")
gfx_print_sx1262_info()
radio = None
try:
    radio = make_radio(FREQUENCY, BANDWIDTH, SPREADING_FACTOR, CODING_RATE,
                       SYNC_WORD, OUTPUT_POWER, PREAMBLE_LENGTH, False)
    radio.start_receive()
    print("SX1262 initialization successful")
    initialization_successful = True
except OSError as error:
    print("SX1262 initialization failed")
    print("Error code: %s" % error)
    initialization_successful = False

gfx_print_init(initialization_successful)
display.show(SSD1681.FULL_REFRESH)
refresh_flag = True

while True:
    now = time.ticks_ms()
    if not button.value():
        refresh_flag = True
        send_flag = True
        connection_state = CONNECTING
        error_count = 0
        send_at = time.ticks_add(now, 1000)

    if initialization_successful and refresh_flag:
        refresh_flag = False
        gfx_print_transmission()
        display.show(SSD1681.FAST_REFRESH)

    if initialization_successful and send_flag and time.ticks_diff(now, send_at) > 0:
        send_flag = False
        print("[SX1262] Sending another packet ... ")
        led_send.value(0)
        send_led_off_at = time.ticks_add(now, 50)
        radio.transmit(make_packet(send_data))
        radio.start_receive()

    if send_led_off_at and time.ticks_diff(now, send_led_off_at) > 0:
        led_send.value(1)
        send_led_off_at = 0
    if receive_led_off_at and time.ticks_diff(now, receive_led_off_at) > 0:
        led_receive.value(1)
        receive_led_off_at = 0

    if initialization_successful and radio.poll():
        packet = radio.read()
        if packet and len(packet) == 16 and packet[0:4] == b"MAC:":
            incoming_mac_0 = int.from_bytes(packet[8:12], "big")
            incoming_mac_1 = int.from_bytes(packet[4:8], "big")
            if incoming_mac_0 != local_mac[0] and incoming_mac_1 != local_mac[1]:
                peer_mac[0] = incoming_mac_0
                peer_mac[1] = incoming_mac_1
                receive_data = int.from_bytes(packet[12:16], "big")
                print("[SX1262] Received packet")
                for index, value in enumerate(packet):
                    print("[SX1262] Data[%d]: 0X%X" % (index, value))
                receive_rssi = radio.last_rssi
                receive_snr = radio.last_snr
                print("[SX1262] RSSI: %.1f dBm" % receive_rssi, end="")
                print("[SX1262] SNR: %.1f dB" % receive_snr, end="")
                send_data = (receive_data + 1) & 0xFFFFFFFF
                send_flag = True
                connection_state = CONNECTED
                refresh_flag = True
                led_receive.value(0)
                receive_led_off_at = time.ticks_add(now, 50)
                error_count = 0
                send_at = time.ticks_add(now, 100)
        radio.start_receive()

    if initialization_successful and time.ticks_diff(now, watchdog_at) > 0:
        error_count += 1
        if error_count == 11:
            refresh_flag = True
        if error_count > 10:
            error_count = 11
            send_data = 0
            connection_state = UNCONNECTED
        watchdog_at = time.ticks_add(now, 1000)
    time.sleep_ms(1)
