from machine import Pin
import time
from example_helpers import make_radio
from t_echo_lite_config import nRF52840_BOOT, power_on, unique_device_id

power_on()
print("Ciallo")
button = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
identity = unique_device_id()
local_mac_0 = int.from_bytes(identity[0:4], "big")
local_mac_1 = int.from_bytes(identity[4:8], "big")


def make_packet(value):
    # Match the Arduino packet layout: DEVICEID[1], then DEVICEID[0].
    return (b"MAC:" + identity[4:8] + identity[0:4] +
            (value & 0xFFFFFFFF).to_bytes(4, "big"))


print("[SX1262] Initializing ... ")
while True:
    try:
        radio = make_radio(914.9, 500.0, 12, 8, 0xAB, 22, 16, False)
        radio.set_current_limit(140)
        break
    except OSError:
        print("SX1262 initialization failed")
        time.sleep(1)
print("SX1262 initialization successful")
send_data = 0
send_pending = True
send_at = time.ticks_add(time.ticks_ms(), 1000)

while True:
    now = time.ticks_ms()
    if not button.value():
        send_pending = True
        send_at = time.ticks_add(now, 1000)
    if send_pending and time.ticks_diff(now, send_at) >= 0:
        send_pending = False
        print("[SX1262] Sending another packet ... ")
        radio.transmit(make_packet(send_data))
        radio.start_receive()

    if radio.poll():
        packet = radio.read()
        valid_peer = False
        if packet and len(packet) == 16 and packet[:4] == b"MAC:":
            incoming_mac_0 = int.from_bytes(packet[8:12], "big")
            incoming_mac_1 = int.from_bytes(packet[4:8], "big")
            valid_peer = (incoming_mac_0 != local_mac_0 and
                          incoming_mac_1 != local_mac_1)

        if valid_peer:
            received = int.from_bytes(packet[12:16], "big")
            print("[SX1262] Received packet!")
            for index, value in enumerate(packet):
                print("[SX1262] Data[%d]: 0X%X" % (index, value))
            print("[SX1262] Data:\t\t%d" % received)
            print("[SX1262] RSSI:\t\t%.1f dBm" % radio.last_rssi)
            print("[SX1262] SNR:\t\t%.1f dB" % radio.last_snr)
            send_data = (received + 1) & 0xFFFFFFFF
            send_pending = True
            send_at = time.ticks_add(time.ticks_ms(), 1000)
        else:
            radio.start_receive()

    time.sleep_ms(1)
