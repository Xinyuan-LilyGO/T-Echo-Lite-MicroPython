"""AW21009 nine-channel, 12-bit LED driver."""

import time


class AW21009:
    def __init__(self, i2c, address=0x20):
        self.i2c = i2c
        self.address = address

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value,)))

    def begin(self, current=255):
        if self.address not in self.i2c.scan():
            raise OSError("AW21009 not found")
        self._write(0x70, 0x00)
        time.sleep_ms(3)
        self._write(0x20, 0x05)  # 12-bit PWM, chip enabled.
        time.sleep_us(250)
        self._write(0x58, current)
        for channel in range(9):
            self._write(0x46 + channel, 0xFF)
        self._write(0x45, 0)
        return True

    def brightness(self, channel, value):
        value = max(0, min(4095, int(value)))
        channels = range(9) if channel is None else (channel,)
        for item in channels:
            self._write(0x21 + item * 2, value & 0xFF)
            self._write(0x22 + item * 2, value >> 8)
        self._write(0x45, 0)

    def off(self):
        self.brightness(None, 0)

