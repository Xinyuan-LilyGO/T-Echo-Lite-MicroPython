import time
from example_helpers import make_radio
from t_echo_lite_config import power_on

power_on()
print("Ciallo")
print("[SX1262] Initializing ... ")
while True:
    try:
        radio = make_radio(868.0, 125.0, 12, 6, 0xAB, 22, 16, False)
        break
    except OSError:
        print("SX1262 initialization failed")
        time.sleep(1)
print("SX1262 initialization successful")
radio.set_current_limit(140)
radio.continuous_wave()
while True:
    pass
