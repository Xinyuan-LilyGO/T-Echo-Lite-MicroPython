import time
from example_helpers import shared_i2c
from t_echo_lite_config import power_on

power_on()
print("Ciallo")
i2c = shared_i2c()
while True:
    found = set(i2c.scan())
    print("Scanning for I2C devices ...")
    print("      " + "".join("0x%02X|" % i for i in range(16)))
    for base in range(0, 128, 16):
        print("0x%02X |" % base + "".join("0x%02X|" % (base + i) if base + i in found else " -- |" for i in range(16)))
    time.sleep(1)
