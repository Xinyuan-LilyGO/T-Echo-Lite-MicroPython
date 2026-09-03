import time
from example_helpers import setup_gps
from nmea import NMEA, cardinal, course_to, distance_between

LONDON = (51.508131, -0.128002)
uart = setup_gps()
gps = NMEA()
print("Ciallo")
print("FullExample.ino")
print("An extensive example of many interesting TinyGPSPlus features")
print("Testing TinyGPSPlus library v. MicroPython NMEA")
print("by Mikal Hart")
print()
print("Sats HDOP  Latitude   Longitude   Fix  Date       Time     Date Alt    Course Speed Card  Distance Course Card  Chars Sentences Checksum")
print("           (deg)      (deg)       Age                      Age  (m)    --- from GPS ----  ---- to London  ----  RX    RX        Fail")
print("----------------------------------------------------------------------------------------------------------------------------------------")

while True:
    deadline = time.ticks_add(time.ticks_ms(), 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        data = uart.read()
        if data:
            gps.feed(data)
    if gps.valid:
        distance = distance_between(gps.latitude, gps.longitude, *LONDON) / 1000
        bearing = course_to(gps.latitude, gps.longitude, *LONDON)
        row = (gps.satellites, gps.hdop, gps.latitude, gps.longitude, gps.age(),
               gps.date, gps.utc, gps.altitude_m, gps.course_deg, gps.speed_kmph,
               cardinal(gps.course_deg or 0), distance, bearing, cardinal(bearing),
               gps.chars, gps.sentences, gps.failed_checksum)
    else:
        row = (gps.satellites, gps.hdop, "*", "*", "*", gps.date, gps.utc,
               "*", "*", "*", "*", "*", "*", "*", gps.chars,
               gps.sentences, gps.failed_checksum)
    print(*row)
    if time.ticks_ms() > 5000 and gps.chars < 10:
        print("No GPS data received: check wiring")
