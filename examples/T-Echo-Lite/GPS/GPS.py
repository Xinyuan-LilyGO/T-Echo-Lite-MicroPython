import time
from example_helpers import setup_gps
from nmea import NMEA

uart = setup_gps()
gps = NMEA()
start = time.ticks_ms()
print("Ciallo")
print("DeviceExample.ino")
print("A simple demonstration of TinyGPSPlus with an attached GPS module")
print("Testing TinyGPSPlus library v. MicroPython NMEA")
print("by Mikal Hart")
print()

while True:
    data = uart.read()
    if data:
        gps.feed(data)
        if gps.utc:
            location = "%.6f,%.6f" % (gps.latitude, gps.longitude) if gps.valid else "INVALID"
            date = "%02d/%02d/%04d" % (gps.date[1], gps.date[2], gps.date[0]) if gps.date else "INVALID"
            utc = "%02d:%02d:%02d.00" % gps.utc
            print("Location: %s  Date/Time: %s %s" % (location, date, utc))
    elif time.ticks_diff(time.ticks_ms(), start) > 5000 and gps.chars < 10:
        print("No GPS detected: check wiring.")
        time.sleep(1)
