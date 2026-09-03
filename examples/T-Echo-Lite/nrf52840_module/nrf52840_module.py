from machine import Pin
import time
from example_helpers import make_flash, make_radio
from t_echo_lite_config import (BATTERY_ADC_DATA,
                                BATTERY_MEASUREMENT_CONTROL, LED_1,
                                RT9080_EN, nRF52840_BOOT, unique_device_id)

SOFTWARE_NAME = "nrf52840_module"
SOFTWARE_LASTEDITTIME = "202607131624"
BOARD_VERSION = "V1.0"

UNCONNECTED = 0
CONNECTED = 1
CONNECTING = 2

FREQUENCY = 920.0
BANDWIDTH = 125.0
SPREADING_FACTOR = 12
CODING_RATE = 8
SYNC_WORD = 0xAB
OUTPUT_POWER = 22
PREAMBLE_LENGTH = 16
CRC_ENABLED = False


def pin_number(port, number):
    return port * 32 + number


PIN_TEST = (
    pin_number(1, 13), pin_number(1, 15), pin_number(0, 29),
    pin_number(1, 10), pin_number(1, 11), pin_number(1, 12),
    pin_number(0, 3), pin_number(0, 28), pin_number(1, 7),
    pin_number(1, 5), pin_number(1, 3), pin_number(0, 10),
    pin_number(0, 9), pin_number(1, 6), pin_number(1, 4),
    pin_number(1, 2), pin_number(0, 25), pin_number(0, 23),
    pin_number(0, 21), pin_number(0, 19), pin_number(0, 16),
    pin_number(0, 20), pin_number(0, 22),
)


class ButtonScanner:
    SINGLE_CLICK = 1
    DOUBLE_CLICK = 2
    LONG_PRESS = 3

    def __init__(self, pin):
        self.pin = pin
        self.active = False
        self.deadline = 0
        self.next_sample = 0
        self.previous_level = -1
        self.high_count = 0
        self.low_count = 0
        self.paragraph_count = 0

    def poll(self):
        now = time.ticks_ms()
        if not self.active:
            if self.pin.value():
                return None
            self.active = True
            self.deadline = time.ticks_add(now, 1000)
            self.next_sample = now
            self.previous_level = -1
            self.high_count = 0
            self.low_count = 0
            self.paragraph_count = 0
            print("Press button to trigger start")

        if time.ticks_diff(now, self.next_sample) > 0:
            level = self.pin.value()
            if level:
                self.high_count += 1
            else:
                self.low_count += 1
            if level != self.previous_level:
                self.paragraph_count += 1
                self.previous_level = level
            self.next_sample = time.ticks_add(now, 50)

        if time.ticks_diff(now, self.deadline) <= 0:
            return None

        self.active = False
        print("end")
        print("high_triggered_count: %d" % self.high_count)
        print("low_triggered_count: %d" % self.low_count)
        print("paragraph_triggered_count: %d" % self.paragraph_count)
        if self.paragraph_count == 2:
            return self.SINGLE_CLICK
        if self.paragraph_count == 4:
            return self.DOUBLE_CLICK
        if self.paragraph_count == 1:
            return self.LONG_PRESS
        return None


def set_all(pins, value):
    for pin in pins:
        pin.value(value)


def signed_32(value):
    return value - 0x100000000 if value & 0x80000000 else value


print("Ciallo")
print("[nRF52840_Module_%s][%s]_firmware_%s" %
      (BOARD_VERSION, SOFTWARE_NAME, SOFTWARE_LASTEDITTIME))

power = Pin(RT9080_EN, Pin.OUT, value=0)
time.sleep_ms(5)
power.value(1)
time.sleep_ms(5)

button_pin = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
button = ButtonScanner(button_pin)
Pin(BATTERY_ADC_DATA, Pin.IN)
Pin(BATTERY_MEASUREMENT_CONTROL, Pin.OUT, value=1)

test_pins = [Pin(number, Pin.OUT, value=0) for number in PIN_TEST]
time.sleep_ms(1000)
set_all(test_pins, 1)
time.sleep_ms(1000)
set_all(test_pins, 0)
time.sleep_ms(1000)
set_all(test_pins, 1)
time.sleep_ms(1000)
set_all(test_pins, 0)
time.sleep_ms(2000)
print("pin test finish")

while True:
    flash = None
    raw_jedec_id = None
    try:
        flash = make_flash()
        raw_jedec_id = flash.jedec_id()
        if raw_jedec_id not in (0xBA6016, 0xBA4016):
            raise OSError("unsupported flash JEDEC ID")
        break
    except OSError:
        print("Flash initialization failed")
        if raw_jedec_id is None:
            print("Flash JEDEC ID read failed")
        else:
            print("Raw flash JEDEC ID: 0x%06X" % raw_jedec_id)
        set_all(test_pins, 1)
        time.sleep_ms(1000)

print("Flash initialization successful")
print("Flash JEDEC ID: 0x%X" % flash.jedec_id())
set_all(test_pins, 1)
time.sleep_ms(500)
set_all(test_pins, 0)
time.sleep_ms(1000)

radio = None
try:
    radio = make_radio(FREQUENCY, BANDWIDTH, SPREADING_FACTOR, CODING_RATE,
                       SYNC_WORD, OUTPUT_POWER, PREAMBLE_LENGTH, CRC_ENABLED)
    radio.start_receive()
    print("SX1262 initialization successful")
except OSError as error:
    print("SX1262 initialization failed")
    print("Error code: %s" % error)

if radio is None:
    while True:
        print("SX1262 initialization failed")
        set_all(test_pins, 1)
        time.sleep_ms(1000)

set_all(test_pins, 1)
time.sleep_ms(500)
set_all(test_pins, 0)
time.sleep_ms(1000)

identity = unique_device_id()
local_mac_0 = int.from_bytes(identity[0:4], "big")
local_mac_1 = int.from_bytes(identity[4:8], "big")
peer_mac_0 = 0
peer_mac_1 = 0
send_data = 0
receive_data = 0
connection_state = UNCONNECTED
send_pending = False
send_at = 0
send_indicator_off_at = 0
receive_indicator_off_at = 0


def make_packet(value):
    return (b"MAC:" + identity[4:8] + identity[0:4] +
            (value & 0xFFFFFFFF).to_bytes(4, "big"))


while True:
    now = time.ticks_ms()

    if send_pending and time.ticks_diff(now, send_at) > 0:
        send_pending = False
        print("[SX1262] Sending another packet ... ")
        Pin(LED_1, Pin.OUT, value=0)
        send_indicator_off_at = time.ticks_add(now, 50)
        radio.transmit(make_packet(send_data))
        radio.start_receive()

    if send_indicator_off_at and time.ticks_diff(now, send_indicator_off_at) > 0:
        set_all(test_pins, 0)
        send_indicator_off_at = 0
    if (receive_indicator_off_at and
            time.ticks_diff(now, receive_indicator_off_at) > 0):
        set_all(test_pins, 0)
        receive_indicator_off_at = 0

    if radio.poll():
        packet = radio.read()
        if packet and len(packet) == 16 and packet[0:4] == b"MAC:":
            incoming_mac_0 = int.from_bytes(packet[8:12], "big")
            incoming_mac_1 = int.from_bytes(packet[4:8], "big")
            if incoming_mac_0 != local_mac_0 and incoming_mac_1 != local_mac_1:
                peer_mac_0 = incoming_mac_0
                peer_mac_1 = incoming_mac_1
                receive_data = int.from_bytes(packet[12:16], "big")
                print("[SX1262] Received packet")
                print("[SX1262] Mac0: %d" % signed_32(peer_mac_0))
                print("[SX1262] Mac1: %d" % signed_32(peer_mac_1))
                print("[SX1262] Data: %u" % receive_data)
                print("[SX1262] RSSI: %.1f dBm" % radio.last_rssi)
                print("[SX1262] SNR: %.1f dB" % radio.last_snr, end="")
                send_data = (receive_data + 1) & 0xFFFFFFFF
                send_pending = True
                connection_state = CONNECTED
                set_all(test_pins, 1)
                receive_indicator_off_at = time.ticks_add(now, 50)
                send_at = time.ticks_add(now, 8000)
        radio.start_receive()

    gesture = button.poll()
    if gesture == ButtonScanner.SINGLE_CLICK:
        print("Key triggered: SINGLE_CLICK")
        send_pending = True
        connection_state = CONNECTING
        send_at = time.ticks_add(time.ticks_ms(), 1000)
    elif gesture == ButtonScanner.DOUBLE_CLICK:
        print("Key triggered: DOUBLE_CLICK")
    elif gesture == ButtonScanner.LONG_PRESS:
        print("Key triggered: LONG_PRESS")
    time.sleep_ms(1)
