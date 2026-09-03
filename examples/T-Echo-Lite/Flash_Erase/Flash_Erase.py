import gc
import os
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
print("Flash chip JEDEC ID: 0x%06X" % flash.jedec_id())
print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
print("This sketch will ERASE ALL DATA on the flash chip!")
print("Type OK (all caps) and press enter to continue.")
print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
while "OK" not in input():
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("This sketch will ERASE ALL DATA on the flash chip!")
    print("Type OK (all caps) and press enter to continue.")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    time.sleep(1)
print("Erasing flash chip in 10 seconds...")
print("Note you will see stat and other debug output printed repeatedly.")
print("Let it run for ~30 seconds until the flash erase is finished.")
print("An error or success message will be printed when complete.")

# The source and imported modules are already compiled into RAM. Detach the
# external filesystem before issuing chip erase so the VFS cannot access it.
if os.getcwd().startswith("/flash"):
    os.chdir("/")
gc.collect()
try:
    os.umount("/flash")
except OSError as error:
    print("Failed to unmount /flash: %s" % error)
    raise

try:
    flash.erase_chip()
    print("Successfully erased chip!")
except OSError:
    print("Failed to erase chip!")
    raise
