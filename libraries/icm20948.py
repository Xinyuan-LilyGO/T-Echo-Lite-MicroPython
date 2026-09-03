"""ICM-20948 accelerometer, gyroscope and AK09916 magnetometer driver."""

import math
import struct
import time


class ICM20948:
    def __init__(self, i2c, address=0x68):
        self.i2c = i2c
        self.address = address
        self.bank = -1
        self.gyro_offset = [0.0, 0.0, 0.0]
        self.accel_offset = [0.0, 0.0, 0.0]

    def _select(self, bank):
        if bank != self.bank:
            self.i2c.writeto_mem(self.address, 0x7F, bytes((bank << 4,)))
            self.bank = bank

    def _write(self, bank, register, value):
        self._select(bank)
        self.i2c.writeto_mem(self.address, register, bytes((value,)))

    def _read(self, bank, register, length=1):
        self._select(bank)
        return self.i2c.readfrom_mem(self.address, register, length)

    def begin(self, calibrate=True):
        self._select(0)
        if self._read(0, 0x00)[0] != 0xEA:
            raise OSError("ICM20948 WHO_AM_I mismatch")
        self._write(0, 0x06, 0x80)
        time.sleep_ms(100)
        self._write(0, 0x06, 0x01)
        self._write(0, 0x07, 0x00)
        self._write(2, 0x01, 0x31)  # 2 dps range setting, DLPF enabled.
        self._write(2, 0x00, 0x04)
        self._write(2, 0x14, 0x31)  # +/-2g, DLPF 6.
        self._write(2, 0x10, 0x00)
        self._write(2, 0x11, 0x04)
        self._init_magnetometer()
        if calibrate:
            self.calibrate()
        return True

    def _init_magnetometer(self):
        self._write(0, 0x03, 0x20)
        self._write(3, 0x01, 0x07)
        self._mag_write(0x32, 0x01)
        time.sleep_ms(10)
        self._mag_write(0x31, 0x04)  # Continuous 20 Hz.
        time.sleep_ms(10)
        self._select(3)
        self.i2c.writeto_mem(self.address, 0x03, b"\x8C")
        self.i2c.writeto_mem(self.address, 0x04, b"\x10")
        self.i2c.writeto_mem(self.address, 0x05, b"\x89")
        self.bank = 3

    def _mag_write(self, register, value):
        self._select(3)
        self.i2c.writeto_mem(self.address, 0x03, b"\x0C")
        self.i2c.writeto_mem(self.address, 0x04, bytes((register,)))
        self.i2c.writeto_mem(self.address, 0x06, bytes((value,)))
        self.i2c.writeto_mem(self.address, 0x05, b"\x81")
        time.sleep_ms(10)

    def calibrate(self, samples=100):
        sums_g = [0.0, 0.0, 0.0]
        sums_a = [0.0, 0.0, 0.0]
        for _ in range(samples):
            accel, gyro, _, _ = self.read(raw_offsets=False)
            for index in range(3):
                sums_a[index] += accel[index]
                sums_g[index] += gyro[index]
            time.sleep_ms(5)
        self.gyro_offset = [value / samples for value in sums_g]
        self.accel_offset = [sums_a[0] / samples, sums_a[1] / samples,
                             sums_a[2] / samples - 1.0]

    def read(self, raw_offsets=True):
        data = self._read(0, 0x2D, 23)
        values = struct.unpack(">hhhhhhh", data[:14])
        accel = [values[i] / 16384.0 for i in range(3)]
        gyro = [values[i + 3] / 131.0 for i in range(3)]
        temperature = values[6] / 333.87 + 21.0
        mag = (0.0, 0.0, 0.0)
        ext = data[14:23]
        if len(ext) == 9 and ext[0] & 1 and not ext[8] & 0x08:
            mx, my, mz = struct.unpack("<hhh", ext[1:7])
            mag = (mx * 0.15, my * 0.15, mz * 0.15)
        if raw_offsets:
            accel = [accel[i] - self.accel_offset[i] for i in range(3)]
            gyro = [gyro[i] - self.gyro_offset[i] for i in range(3)]
        return tuple(accel), tuple(gyro), temperature, mag

    def orientation(self):
        accel, gyro, temperature, mag = self.read()
        ax, ay, az = accel
        pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
        roll = math.degrees(math.atan2(ay, az))
        yaw = math.degrees(math.atan2(mag[1], mag[0]))
        if yaw < 0:
            yaw += 360
        return pitch, roll, yaw, accel, gyro, mag, temperature

    def sleep(self, enabled=True):
        value = self._read(0, 0x06)[0]
        self._write(0, 0x06, value | 0x40 if enabled else value & ~0x40)
