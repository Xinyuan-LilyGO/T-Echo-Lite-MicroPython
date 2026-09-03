"""Pin map and bus helpers for LilyGo T-Echo-Lite / KeyShield."""

from machine import ADC, I2C, Pin, SPI, UART, mem32
import time


def _pin(port, number):
    return port * 32 + number


EXT_1x4P_1_IO_0_25 = _pin(0, 25)
EXT_1x4P_1_IO_0_23 = _pin(0, 23)
EXT_1x4P_2_IO_1_2 = _pin(1, 2)
EXT_1x4P_2_IO_1_4 = _pin(1, 4)
EXT_1X7P_IO_1_13 = _pin(1, 13)
EXT_1X7P_IO_1_15 = _pin(1, 15)
EXT_1X7P_IO_0_29 = _pin(0, 29)
EXT_1X7P_IO_1_10 = _pin(1, 10)
EXT_1X7P_IO_1_11 = _pin(1, 11)
EXT_2X5P_1_IO_1_3 = _pin(1, 3)
EXT_2X5P_2_IO_1_6 = _pin(1, 6)
EXT_2X5P_2_IO_0_25 = _pin(0, 25)
EXT_2X5P_2_IO_0_10 = _pin(0, 10)
EXT_2X5P_2_IO_0_23 = _pin(0, 23)
EXT_2X5P_2_IO_0_9 = _pin(0, 9)

IIC_1_SDA = _pin(1, 4)
IIC_1_SCL = _pin(1, 2)

ZD25WQ32C_CS = _pin(0, 12)
ZD25WQ32C_SCLK = _pin(0, 4)
ZD25WQ32C_MOSI = _pin(0, 6)
ZD25WQ32C_MISO = _pin(0, 8)
ZD25WQ32C_IO2 = _pin(1, 9)
ZD25WQ32C_IO3 = _pin(0, 26)

LED_1 = _pin(1, 7)
LED_2 = _pin(1, 5)
LED_3 = _pin(1, 14)

SCREEN_WIDTH = 176
SCREEN_HEIGHT = 192
SCREEN_BS1 = _pin(1, 12)
SCREEN_BUSY = _pin(0, 3)
SCREEN_RST = _pin(0, 28)
SCREEN_DC = _pin(0, 21)
SCREEN_CS = _pin(0, 22)
SCREEN_SCLK = _pin(0, 19)
SCREEN_MOSI = _pin(0, 20)

SX1262_CS = _pin(0, 11)
SX1262_RST = _pin(0, 7)
SX1262_SCLK = _pin(0, 13)
SX1262_MOSI = _pin(0, 15)
SX1262_MISO = _pin(0, 17)
SX1262_BUSY = _pin(0, 14)
SX1262_DIO1 = _pin(1, 8)
SX1262_DIO2 = _pin(0, 5)
SX1262_RF_VC1 = _pin(0, 27)
SX1262_RF_VC2 = _pin(1, 1)

nRF52840_BOOT = _pin(0, 24)
BATTERY_MEASUREMENT_CONTROL = _pin(0, 31)
BATTERY_ADC_DATA = _pin(0, 2)
RT9080_EN = _pin(0, 30)

GPS_WAKE_UP = EXT_1X7P_IO_1_13
GPS_1PPS = EXT_1X7P_IO_1_15
GPS_UART_TX = EXT_1X7P_IO_0_29
GPS_UART_RX = EXT_1X7P_IO_1_10
GPS_RT9080_EN = EXT_1X7P_IO_1_11

ICM20948_ADDRESS = 0x68
ICM20948_INT = _pin(0, 16)
TCA8418_IIC_ADDRESS = 0x34
TCA8418_INT = EXT_2X5P_1_IO_1_3
TCA8418_KEYPAD_SCAN_WIDTH = 4
TCA8418_KEYPAD_SCAN_HEIGHT = 5
ES8311_IIC_ADDRESS = 0x18
ES8311_ADC_DATA = EXT_2X5P_2_IO_0_23
ES8311_DAC_DATA = EXT_2X5P_2_IO_1_6
ES8311_BCLK = EXT_2X5P_2_IO_0_10
ES8311_MCLK = EXT_2X5P_2_IO_0_9
ES8311_WS_LRCK = EXT_2X5P_2_IO_0_25
AW86224_IIC_ADDRESS = 0x58
AW21009_IIC_ADDRESS = 0x20

TCA8418_MAP = (
    "Yes", "*", "0", "#", "Null", "Null", "Null", "Null", "Null", "Null",
    "No", "7", "8", "9", "Null", "Null", "Null", "Null", "Null", "Null",
    "Down", "4", "5", "6", "Null", "Null", "Null", "Null", "Null", "Null",
    "Center", "1", "2", "3", "Null", "Null", "Null", "Null", "Null", "Null",
    "Up", "Esc", "Home", "Mail", "Null", "Null", "Null", "Null", "Null", "Null",
)

# This nRF port expands its 8-bit SAADC result to read_u16().  The calibrated
# full scale below maps the measured MicroPython value 41891 to the Arduino
# 12-bit value 2847. Adjust it if a board-level reference measurement differs.
ADC_CALIBRATED_FULL_SCALE_V = 3.262131
ARDUINO_ADC_REFERENCE_V = 3.0
ARDUINO_ADC_COUNTS = 4096
BATTERY_SETTLE_MS = 300


def power_on(reset=False):
    pin = Pin(RT9080_EN, Pin.OUT, value=1)
    if reset:
        time.sleep_ms(100)
        pin.off()
        time.sleep_ms(100)
        pin.on()
        time.sleep_ms(1000)
    return pin


def shared_i2c(freq=400000):
    return I2C(0, scl=Pin(IIC_1_SCL), sda=Pin(IIC_1_SDA), freq=freq)


def gps_uart():
    return UART(0, 9600, timeout=50, timeout_char=10)


def spi_bus(bus_id, sck, mosi, miso, baudrate=8000000):
    return SPI(bus_id, baudrate=baudrate, polarity=0, phase=0,
               sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))


def battery_adc_read(samples=5, sample_delay_ms=5):
    adc = ADC(Pin(BATTERY_ADC_DATA))
    read_adc = adc.read_u16 if hasattr(adc, "read_u16") else adc.read

    # The first nRF SAADC conversion after enabling the divider can retain a
    # full-scale transient. Discard it, then use the median to reject outliers.
    read_adc()
    time.sleep_ms(sample_delay_ms)
    readings = []
    for _ in range(max(1, samples)):
        readings.append(read_adc())
        time.sleep_ms(sample_delay_ms)
    readings.sort()
    native_raw = readings[len(readings) // 2]
    if native_raw > 16383:
        volts = native_raw * ADC_CALIBRATED_FULL_SCALE_V / 65535.0
    else:
        volts = native_raw * ADC_CALIBRATED_FULL_SCALE_V / 255.0

    # Present the same 12-bit count and voltage formula as the Arduino sketch.
    raw = int(volts * ARDUINO_ADC_COUNTS / ARDUINO_ADC_REFERENCE_V + 0.5)
    raw = max(0, min(ARDUINO_ADC_COUNTS - 1, raw))
    volts = raw * ARDUINO_ADC_REFERENCE_V / ARDUINO_ADC_COUNTS
    return raw, volts, volts * 2.0


def battery_read(disable_after=True):
    enable = Pin(BATTERY_MEASUREMENT_CONTROL, Pin.OUT, value=1)
    time.sleep_ms(BATTERY_SETTLE_MS)
    result = battery_adc_read()
    if disable_after:
        enable.off()
    return result


def unique_device_id():
    # FICR DEVICEID[0:1], unlike this nRF port's empty machine.unique_id().
    # Some nRF MicroPython builds expose mem32 values as signed integers.
    # Convert both register values back to their unsigned 32-bit bit pattern.
    device_id_0 = mem32[0x10000060] & 0xFFFFFFFF
    device_id_1 = mem32[0x10000064] & 0xFFFFFFFF
    return device_id_0.to_bytes(4, "big") + device_id_1.to_bytes(4, "big")


def system_off_on_button():
    # Configure P0.24 SENSE=Low with pull-up, then enter nRF SYSTEMOFF.
    mem32[0x50000700 + 4 * 24] = (3 << 16) | (3 << 2)
    mem32[0x40000500] = 1
    while True:
        pass
