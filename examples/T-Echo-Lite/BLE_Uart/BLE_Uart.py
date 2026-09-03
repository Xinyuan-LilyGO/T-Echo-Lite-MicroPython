import select
import sys
import time
from ble_uart import BleUart, BleUnavailable
from t_echo_lite_config import power_on, unique_device_id

power_on()
central_name = "Central"
next_send = 0


def print_received(data):
    print("[%s]-> " % central_name, end="")
    try:
        sys.stdout.write(data.decode())
    except (UnicodeError, AttributeError):
        sys.stdout.write("".join(chr(value) for value in data))


def received(data):
    print_received(data)


def connected(handle):
    global next_send
    print("Connected to " + central_name)
    next_send = time.ticks_ms()


def disconnected(handle, reason):
    print("\nDisconnected, reason = 0x%02X" % reason)


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


try:
    print("BLE UART Example")
    print("---------------------------\n")
    uart = BleUart(on_receive=received, on_connect=connected,
                   on_disconnect=disconnected)
    uart.start()
    print("Please use the BLE debugging tool to connect to the development board.")
    print("Once connected, enter character(s) that you wish to send")
    serial_poller = make_serial_poller()
    while True:
        now = time.ticks_ms()
        if uart.connected and time.ticks_diff(now, next_send) >= 0:
            uart.write(periodic_message(now))
            next_send = time.ticks_add(now, 1000)

        if uart.connected and serial_poller and serial_poller.poll(0):
            value = sys.stdin.read(1)
            if value:
                uart.write(value)
        time.sleep_ms(2)
except BleUnavailable as error:
    print("BLE initialization failed:", error)
    raise
