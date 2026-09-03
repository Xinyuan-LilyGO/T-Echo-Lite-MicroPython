import time
from example_helpers import shared_i2c
from icm20948 import ICM20948
from t_echo_lite_config import ICM20948_ADDRESS, power_on

power_on()
print("Ciallo")
imu = ICM20948(shared_i2c(), ICM20948_ADDRESS)
while True:
    try:
        imu.begin(calibrate=False)
        break
    except OSError:
        print("ICM20948 AG initialization failed")
        time.sleep(1)
print("ICM20948 initialization successful")
print("Position your ICM20948 flat and don't move it - calibrating...")
time.sleep(1)
imu.calibrate()
print("Done!")

while True:
    pitch, roll, yaw, accel, gyro, mag, temperature = imu.orientation()
    print("G values (x,y,z):")
    print("%.3f   %.3f   %.3f" % accel)
    print("Angles (x,y,z):")
    print("%.2f   %.2f   %.2f" % (roll, pitch, yaw))
    print("Pitch = %.2f  |  Roll = %.2f  |  Yaw = %.2f" % (pitch, roll, yaw))
    print()
    print()
    time.sleep_ms(100)
