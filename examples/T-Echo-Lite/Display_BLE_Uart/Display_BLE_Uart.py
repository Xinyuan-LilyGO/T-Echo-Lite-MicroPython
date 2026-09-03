import select
import sys
import time
from ble_uart import BleUart, BleUnavailable
from example_helpers import make_display
from gfx_resources import FREEMONO9PT7B, FREEMONOBOLD9PT7B, FREESANS9PT7B, ORG_01
from ssd1681 import SSD1681
from t_echo_lite_config import SCREEN_HEIGHT, SCREEN_WIDTH, power_on, unique_device_id

power_on()
display = make_display()
display.begin()
received_data = b""
central_name = "Central"
connection_refresh = False
transmission_refresh = False
next_send = 0


def draw(text, x, y, font, size=1, color=0):
    return display.gfx_font_text(text, x, y, font, color, size)


def gfx_print_test(text):
    display.fill(1)
    draw("TEST", SCREEN_WIDTH // 4 + 5, SCREEN_HEIGHT // 4 - 15,
         FREESANS9PT7B, 2)
    draw(text, 20, SCREEN_HEIGHT // 4 + 10, FREEMONO9PT7B)
    draw("3", SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.FULL_REFRESH)
    time.sleep_ms(200)

    display.fill_rect(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 20,
                      30, 40, 1)
    draw("2", SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.PARTIAL_REFRESH)
    display.show(SSD1681.PARTIAL_REFRESH)
    time.sleep_ms(200)

    display.fill_rect(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2 + 20,
                      30, 30, 1)
    draw("1", SCREEN_WIDTH // 2 + 3, SCREEN_HEIGHT // 2 + 40, ORG_01, 4)
    display.show(SSD1681.PARTIAL_REFRESH)
    display.show(SSD1681.PARTIAL_REFRESH)
    time.sleep_ms(200)


def gfx_print_ble_uart_info():
    display.fill(1)
    draw("BLE Uart Info", 25, 15, FREEMONOBOLD9PT7B)
    draw("<-----------Receive Info-----------> ", 10, 105, ORG_01)


def gfx_print_init(success):
    display.fill_rect(0, 23, SCREEN_WIDTH, 40, 1)
    if success:
        draw("[Status]: Init successful", 10, 28, ORG_01)
        draw("[BLE Name]: T-Echo-Lite-nRF52840", 10, 35, ORG_01)
        draw("[Uart Serivce]: 6E400001......", 10, 49, ORG_01)
        draw("[Uart RX]: 6E400002......", 10, 56, ORG_01)
        draw("[Uart TX]: 6E400003......", 10, 63, ORG_01)
        draw("[Local MAC]: " + unique_device_id().hex().upper(),
             10, 77, ORG_01)
    else:
        draw("[Status]: Init failed", 10, 28, ORG_01)


def gfx_print_connection(connected):
    display.fill_rect(0, 86, SCREEN_HEIGHT, 14, 1)
    draw("[Connect]: " + ("Connected" if connected else "Unconnected"),
         10, 91, ORG_01)


def received_text(data):
    return "".join(chr(value) for value in data)


def gfx_print_transmission(connected):
    display.fill_rect(0, 107, SCREEN_HEIGHT, 42, 1)
    if connected:
        draw("[Receive Data]: ", 10, 112, ORG_01)
        draw("[" + central_name + "]-> " + received_text(received_data),
             20, 119, ORG_01)
    else:
        draw("[Receive Data]: null", 10, 112, ORG_01)


def received(data):
    global received_data, transmission_refresh
    received_data = data
    print("[%s]-> " % central_name, end="")
    try:
        print(data.decode(), end="")
    except (UnicodeError, AttributeError):
        print(repr(data), end="")
    transmission_refresh = True


def connected(handle):
    global connection_refresh, next_send
    print("Connected to " + central_name)
    connection_refresh = True
    next_send = time.ticks_ms()


def disconnected(handle, reason):
    global connection_refresh, transmission_refresh
    print("\nDisconnected, reason = 0x%X" % reason)
    connection_refresh = True
    transmission_refresh = True


def periodic_message(now):
    return ("BLE Test \n[T-Echo-Lite MAC ID]: %s\n"
            "[MCU Running time]: %u s\n" %
            (unique_device_id().hex().upper(), now // 1000))


def make_serial_poller():
    try:
        poller = select.poll()
        poller.register(sys.stdin, select.POLLIN)
        return poller
    except (AttributeError, OSError):
        return None


print("Ciallo")
gfx_print_test("BLE Uart test")
gfx_print_ble_uart_info()
uart = None
try:
    uart = BleUart(on_receive=received, on_connect=connected,
                   on_disconnect=disconnected)
    uart.start()
    print("BLE initialization successful")
    print("Please use the BLE debugging tool to connect to the development board.")
    print("Once connected, enter character(s) that you wish to send")
    initialization_successful = True
except BleUnavailable:
    print("BLE initialization failed")
    initialization_successful = False

gfx_print_init(initialization_successful)
gfx_print_connection(False)
gfx_print_transmission(False)
display.show(SSD1681.FULL_REFRESH)
serial_poller = make_serial_poller()

while True:
    if uart is None:
        time.sleep_ms(100)
        continue

    if connection_refresh:
        gfx_print_connection(uart.connected)
        display.show(SSD1681.FAST_REFRESH)
        connection_refresh = False

    if transmission_refresh:
        gfx_print_transmission(uart.connected)
        display.show(SSD1681.FAST_REFRESH)
        transmission_refresh = False

    now = time.ticks_ms()
    if uart.connected and time.ticks_diff(now, next_send) >= 0:
        uart.write(periodic_message(now))
        next_send = time.ticks_add(now, 1000)

    if uart.connected and serial_poller and serial_poller.poll(0):
        value = sys.stdin.read(1)
        if value:
            time.sleep_ms(2)
            uart.write(value)
    time.sleep_ms(1)
