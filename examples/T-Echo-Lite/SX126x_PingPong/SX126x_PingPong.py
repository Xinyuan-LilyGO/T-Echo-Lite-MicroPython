import time
from example_helpers import make_radio
from t_echo_lite_config import power_on

INITIATING_NODE = True
power_on()
print("Ciallo")
print("[SX1262] Initializing ... ")
while True:
    try:
        radio = make_radio(868.6, 125.0, 9, 6, 0xAB, 22, 16, False)
        break
    except OSError:
        print("SX1262 initialization failed")
        time.sleep(1)
print("SX1262 initialization successful")

if INITIATING_NODE:
    print("[SX1262] Sending first packet ... ", end="")
    transmission_ok = radio.transmit("Hello World!")
else:
    print("[SX1262] Starting to listen ... ")
    transmission_ok = None

while True:
    if transmission_ok is not None:
        print("transmission finished!" if transmission_ok else "failed, code -1")
        transmission_ok = None
    packet = radio.receive(10000)
    if packet:
        print("[SX1262] Received packet!")
        print("[SX1262] Data:\t\t" + packet.decode())
        print("[SX1262] RSSI:\t\t%.1f dBm" % radio.last_rssi)
        print("[SX1262] SNR:\t\t%.1f dB" % radio.last_snr)
        time.sleep(1)
        print("[SX1262] Sending another packet ... ")
        transmission_ok = radio.transmit("Hello World!")
