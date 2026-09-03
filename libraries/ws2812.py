"""WS2812 driver using 3.2 MHz SPI symbol expansion."""

import time


class WS2812:
    def __init__(self, spi, count, brightness=255):
        self.spi = spi
        self.count = count
        self.brightness = brightness
        self.pixels = [(0, 0, 0)] * count

    @staticmethod
    def _byte(value):
        output = bytearray(4)
        for index in range(4):
            pair = (value >> (6 - index * 2)) & 3
            output[index] = (0x88, 0x8E, 0xE8, 0xEE)[pair]
        return output

    def set(self, index, red, green, blue):
        self.pixels[index] = (red, green, blue)

    def fill(self, color):
        self.pixels = [color] * self.count

    def show(self):
        output = bytearray(self.count * 12)
        offset = 0
        for red, green, blue in self.pixels:
            for value in (green, red, blue):
                value = value * self.brightness // 255
                encoded = self._byte(value)
                output[offset:offset + 4] = encoded
                offset += 4
        self.spi.write(output)
        time.sleep_us(80)

    @staticmethod
    def hsv(hue, saturation=255, value=255):
        hue = (hue % 65536) * 6
        sector, fraction = divmod(hue, 65536)
        p = value * (255 - saturation) // 255
        q = value * (255 - saturation * fraction // 65536) // 255
        t = value * (255 - saturation * (65535 - fraction) // 65536) // 255
        return ((value, t, p), (q, value, p), (p, value, t),
                (p, q, value), (t, p, value), (value, p, q))[sector]
