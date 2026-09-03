import time
from example_helpers import make_flash
from t_echo_lite_config import power_on

power_on()
print("Ciallo")
print("Adafruit Serial Flash Info example")
while True:
    try:
        flash = make_flash()
        break
    except OSError:
        print("Flash initialization failed")
        time.sleep(1)
print("Flash initialization successful")
while True:
    print("JEDEC ID: 0x%06X" % flash.jedec_id())
    print("Flash size: %d KB" % (flash.size() // 1024))
    time.sleep(1)
