"""Factory functions shared by the converted examples."""

from machine import Pin
from t_echo_lite_config import *


def make_display():
    from ssd1681 import SSD1681
    # SPIM1 is kept separate from I2C0, LoRa SPIM2 and filesystem SPIM3.
    spi = spi_bus(1, SCREEN_SCLK, SCREEN_MOSI, SCREEN_MOSI, 8000000)
    return SSD1681(spi, SCREEN_CS, SCREEN_DC, SCREEN_RST, SCREEN_BUSY,
                   SCREEN_BS1, rotation=1)


def make_radio(frequency=868.6, bandwidth=125.0, sf=9, cr=6,
               sync_word=0xAB, power=22, preamble=16, crc=False):
    from sx1262 import SX1262
    spi = spi_bus(2, SX1262_SCLK, SX1262_MOSI, SX1262_MISO, 8000000)
    radio = SX1262(spi, SX1262_CS, SX1262_BUSY, SX1262_RST, SX1262_DIO1,
                   SX1262_RF_VC1, SX1262_RF_VC2)
    radio.begin(frequency, bandwidth, sf, cr, sync_word, power, preamble, crc)
    return radio


def make_flash():
    from spi_nor import SpiNor
    spi = spi_bus(3, ZD25WQ32C_SCLK, ZD25WQ32C_MOSI,
                  ZD25WQ32C_MISO, 8000000)
    flash = SpiNor(spi, ZD25WQ32C_CS)
    flash.wake()
    return flash


def display_lines(display, title, lines, mode=None):
    from ssd1681 import SSD1681
    display.fill(1)
    display.text(title[:23], 2, 2, 0)
    display.hline(0, 12, display.width, 0)
    y = 18
    for line in lines:
        display.text(str(line)[:24], 2, y, 0)
        y += 11
        if y > display.height - 8:
            break
    display.show(SSD1681.FULL_REFRESH if mode is None else mode)


def setup_gps():
    power_on()
    Pin(GPS_RT9080_EN, Pin.OUT, value=1)
    Pin(GPS_WAKE_UP, Pin.OUT, value=1)
    Pin(GPS_1PPS, Pin.IN)
    return gps_uart()

