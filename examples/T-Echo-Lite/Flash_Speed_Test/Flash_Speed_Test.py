import time
from example_helpers import make_flash
from t_echo_lite_config import power_on

TEST_WHOLE_CHIP = False
BUFFER_SIZE = 4096


def speed(label, count, elapsed):
    seconds = elapsed / 1000.0
    print("%s %d bytes in %.2f seconds" % (label, count, seconds))
    print("Speed: %.2f KB/s\n" % (count / max(seconds, 0.001) / 1000.0))


def write_and_compare(flash, pattern):
    size = flash.size() if TEST_WHOLE_CHIP else BUFFER_SIZE
    start_address = 0 if TEST_WHOLE_CHIP else flash.size() - BUFFER_SIZE
    print("Erase chip" if TEST_WHOLE_CHIP else "Erase scratch sector")
    flash.erase_chip() if TEST_WHOLE_CHIP else flash.erase_sector(start_address)
    block = bytes((pattern,)) * BUFFER_SIZE
    print("Write flash with 0x%02X" % pattern)
    print("Read flash and compare")
    start = time.ticks_ms()
    for address in range(start_address, start_address + size, BUFFER_SIZE):
        flash.write(address, block)
    speed("Write", size, time.ticks_diff(time.ticks_ms(), start))
    start = time.ticks_ms()
    for address in range(start_address, start_address + size, BUFFER_SIZE):
        if flash.read(address, BUFFER_SIZE) != block:
            raise OSError("Flash mismatch at 0x%06X" % address)
    speed("Read", size, time.ticks_diff(time.ticks_ms(), start))


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
print("Adafruit Serial Flash Speed Test example")
print("JEDEC ID: 0x%06X" % flash.jedec_id())
print("Flash size:", flash.size())
write_and_compare(flash, 0xAA)
write_and_compare(flash, 0x55)
print("Speed test is completed.")
while True:
    print("JEDEC ID: 0x%06X" % flash.jedec_id())
    print("Flash size: %d KB" % (flash.size() // 1024))
    time.sleep(1)
