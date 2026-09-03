"""MicroPython port of T-Echo-Lite-KeyShield/general_test.ino."""

import gc
import os
import time
from machine import ADC, Pin, sleep

from example_helpers import make_display, shared_i2c
from keyshield_ui import KeyShieldUI
from t_echo_lite_config import (
    ADC_CALIBRATED_FULL_SCALE_V,
    ARDUINO_ADC_COUNTS,
    ARDUINO_ADC_REFERENCE_V,
    AW21009_IIC_ADDRESS,
    AW86224_IIC_ADDRESS,
    BATTERY_ADC_DATA,
    BATTERY_MEASUREMENT_CONTROL,
    BATTERY_SETTLE_MS,
    ES8311_ADC_DATA,
    ES8311_BCLK,
    ES8311_DAC_DATA,
    ES8311_IIC_ADDRESS,
    ES8311_MCLK,
    ES8311_WS_LRCK,
    GPS_RT9080_EN,
    ICM20948_ADDRESS,
    LED_1,
    LED_2,
    TCA8418_IIC_ADDRESS,
    TCA8418_INT,
    TCA8418_KEYPAD_SCAN_HEIGHT,
    TCA8418_KEYPAD_SCAN_WIDTH,
    TCA8418_MAP,
    nRF52840_BOOT,
    power_on,
    unique_device_id,
)
from example_helpers import setup_gps


BUILD_TIME = "202608181716"
PAGES = ("Home", "Keyboard", "Audio", "Battery",
         "Bluetooth", "LoRa", "GPS", "IMU")
AUTO_SLEEP_MS = 20000
HOME_SCROLL_STEP = 5
LORA_BANDWIDTHS = (7.81, 10.42, 15.63, 20.83, 31.25,
                   41.67, 62.5, 125.0, 250.0, 500.0)
LORA_AUTO_SEND_MS = 5000
LORA_TEXT_MAX = 7
AUDIO_RECORD_PATH = "/flash/general_test_record.tela"
AUDIO_RECORD_MS = 3000
AUDIO_RECORD_STORAGE_BYTES = 70 * 1024
AUDIO_FLASH_RESERVE_BYTES = 64 * 1024


print("[T-Echo-Lite-KeyShield_v1.0][general_test]_firmware_" + BUILD_TIME)
power_on(reset=True)
Pin(BATTERY_MEASUREMENT_CONTROL, Pin.OUT, value=1)
time.sleep_ms(BATTERY_SETTLE_MS)

# cpp_bus_driver uses kDefaultI2cFreqHz (100 kHz) for every KeyShield
# peripheral, including ES8311. Keep the shared Wire-compatible bus identical.
i2c = shared_i2c(100000)
display = make_display()
display.begin()
ui = KeyShieldUI(display)

page = 0
page_selected = False
home_scroll = 0
battery_scroll = 0
bluetooth_scroll = 0
keyboard_history = []
last_action = time.ticks_ms()
filtered_battery = None
battery_info_snapshot = None

keyboard = None
key_irq = Pin(TCA8418_INT, Pin.IN, Pin.PULL_UP)
backlight = None
haptic = None
codec = None
codec_failed = False
ble = None
ble_status_changed = False
ble_rx_pending = []
ble_rx_packets = 0
ble_rx_bytes = 0
flash_ready = False
record_available = False

radio = None
radio_init_attempted = False
lora_frequency = 868.0
lora_bandwidth = 125.0
lora_frequency_text = "868"
lora_bandwidth_text = "125"
lora_control = 0
lora_frequency_editing = False
lora_bandwidth_editing = False
lora_auto_send = False
lora_next_send = 0
lora_tx_counter = 0
lora_rx_count = 0
lora_rx_data = "none"
lora_rssi = None
lora_snr = None
lora_tx_led_deadline = 0
lora_rx_led_deadline = 0

gps_uart = None
gps_parser = None
gps_enter_ms = 0
gps_module_found = False
gps_wait_seconds = -1

imu = None
imu_found = False
imu_values = None

audio_target = 0
audio_status = "Select Mic or Speaker"
audio_action_running = False


def log(message):
    print(message)
    if ble is not None:
        try:
            ble.write(str(message) + "\n")
        except OSError:
            pass


def _init_keyboard():
    global keyboard
    try:
        from tca8418 import TCA8418
        if TCA8418_IIC_ADDRESS not in i2c.scan():
            print("tca8418.Init fail")
            return
        keyboard = TCA8418(i2c, TCA8418_IIC_ADDRESS, TCA8418_MAP)
        keyboard.begin(TCA8418_KEYPAD_SCAN_HEIGHT,
                       TCA8418_KEYPAD_SCAN_WIDTH)
    except OSError:
        keyboard = None
        print("tca8418 config fail")


def _init_backlight(brightness):
    global backlight
    try:
        from aw21009 import AW21009
        if backlight is None:
            backlight = AW21009(i2c, AW21009_IIC_ADDRESS)
            backlight.begin()
        backlight.brightness(None, brightness)
    except OSError:
        backlight = None
        print("aw21009 config fail")


def _init_haptic():
    global haptic
    try:
        from aw86224 import AW86224
        haptic = AW86224(i2c, AW86224_IIC_ADDRESS)
        haptic.begin()
    except OSError:
        haptic = None
        print("aw86224.Init fail")
        return
    try:
        detected_f0 = haptic.get_f0_detection()
        if detected_f0:
            print("aw86224 f0 reference: %u.%uHz" %
                  (detected_f0 // 10, detected_f0 % 10))
        else:
            print("aw86224 f0 reference read fail")
        print("aw86224 selected ram library: %s" % haptic.LIBRARY_NAME)
        haptic.init_ram_mode()
    except OSError:
        print("aw86224 f0 reference read fail")


def start_vibration():
    if haptic is None:
        print("StartVibration failed")
        return
    try:
        haptic.play_ram_waveform(1, 1, 255, auto_brake=True)
    except OSError:
        print("StartVibration failed")


def completion_vibration():
    if haptic is None:
        print("StartCompletionVibration first vibration failed")
        print("StartCompletionVibration second vibration failed")
        return
    try:
        haptic.play_ram_waveform(1, 1, 255, auto_brake=False)
    except (OSError, MemoryError, ValueError):
        print("StartCompletionVibration first vibration failed")
    time.sleep_ms(100)
    try:
        haptic.play_ram_waveform(1, 1, 255, auto_brake=True)
    except (OSError, MemoryError, ValueError):
        print("StartCompletionVibration second vibration failed")


def _init_flash():
    global flash_ready, record_available
    flash_ready = False
    record_available = False

    existing_size = 0
    try:
        existing_size = os.stat(AUDIO_RECORD_PATH)[6]
    except OSError:
        pass
    if codec is not None:
        record_available = codec.recording_info(AUDIO_RECORD_PATH) is not None

    # _boot.py has already mounted the external ZD25 flash at /flash. Calling
    # mount() again can report EBUSY on this nRF VFS and incorrectly disable
    # recording, even while this script is executing from the mounted volume.
    try:
        stat = os.statvfs("/flash")
        total_bytes = stat[0] * stat[2]
        free_bytes = stat[0] * stat[3]
    except (OSError, AttributeError, IndexError) as error:
        print("flash init failed:", error)
        return

    required_bytes = AUDIO_RECORD_STORAGE_BYTES + AUDIO_FLASH_RESERVE_BYTES
    if free_bytes + existing_size < required_bytes:
        print("flash init failed: only %u bytes free, %u required" % (
            free_bytes + existing_size, required_bytes))
        return

    # Reuse the block device created by _boot.py. A failed JEDEC re-query is
    # diagnostic only: a mounted filesystem with enough space remains usable.
    try:
        import t_echo_spiflash
        flash = getattr(t_echo_spiflash, "_bdev", None)
        if flash is not None:
            # Arduino runs this flash bus at 32 MHz. The frozen MicroPython
            # block driver mounts it at a conservative 8 MHz; raising only the
            # already-mounted SPIM3 clock keeps LittleFS ownership intact while
            # improving the audio stream's write bandwidth.
            try:
                flash._spi.init(baudrate=32000000, polarity=0, phase=0)
            except (OSError, ValueError, AttributeError):
                pass
            jedec = int.from_bytes(flash.jedec_id(), "big")
            print("flash JEDEC ID: 0x%06X" % jedec)
        else:
            print("flash filesystem ready: %u bytes" % total_bytes)
    except (ImportError, OSError, AttributeError) as error:
        print("flash JEDEC read failed:", error)
    flash_ready = True


def _ble_connected(handle):
    global ble_status_changed, last_action
    print("BLE Connected")
    ui.ble_connected = True
    last_action = time.ticks_ms()
    ble_status_changed = True


def _ble_disconnected(handle, reason):
    global ble_status_changed, last_action
    print("\nBLE Disconnected, reason = 0x%02X" % reason)
    ui.ble_connected = False
    last_action = time.ticks_ms()
    ble_status_changed = True


def _ble_received(data):
    # The ubluepy callback runs from the SoftDevice event path. Defer console
    # output and notification echo until the normal application loop.
    if len(ble_rx_pending) >= 4:
        del ble_rx_pending[0]
    ble_rx_pending.append(data)


def _init_ble():
    global ble
    try:
        from ble_uart import BleUart
        ble = BleUart(name="T-Echo-Lite-KeyShield",
                      on_receive=_ble_received,
                      on_connect=_ble_connected,
                      on_disconnect=_ble_disconnected)
        ble.start()
        print("BLE initialization successful")
        print("BLE UART ready, please connect with BLE debugging tool")
    except (ImportError, RuntimeError, OSError):
        ble = None
        print("BLE initialization failed")


def process_ble():
    global ble_rx_packets, ble_rx_bytes, last_action
    changed = False
    while ble_rx_pending:
        data = ble_rx_pending.pop(0)
        ble_rx_packets += 1
        ble_rx_bytes += len(data)
        last_action = time.ticks_ms()
        print("[BLE UART RX]-> ", end="")
        try:
            print(data.decode(), end="")
        except (UnicodeError, AttributeError):
            print("".join("%02X " % value for value in data), end="")
        if not data or data[-1] not in (10, 13):
            print()
        if ble is not None:
            try:
                if ble.write(data):
                    print("[BLE UART TX echo]: %u byte(s)" % len(data))
            except OSError as error:
                print("BLE UART echo failed:", error)
        changed = True
    return changed


def read_battery_info():
    adc = ADC(Pin(BATTERY_ADC_DATA))
    read_adc = adc.read_u16 if hasattr(adc, "read_u16") else adc.read
    read_adc()
    time.sleep_ms(5)
    native_sum = 0
    for _ in range(16):
        native_sum += read_adc()
        time.sleep_ms(2)
    native_average = native_sum / 16.0
    if native_average > 16383:
        adc_voltage = native_average * ADC_CALIBRATED_FULL_SCALE_V / 65535.0
    else:
        adc_voltage = native_average * ADC_CALIBRATED_FULL_SCALE_V / 255.0
    raw = int(adc_voltage * ARDUINO_ADC_COUNTS /
              ARDUINO_ADC_REFERENCE_V + 0.5)
    raw = max(0, min(ARDUINO_ADC_COUNTS - 1, raw))
    adc_voltage = raw * ARDUINO_ADC_REFERENCE_V / ARDUINO_ADC_COUNTS
    battery_voltage = adc_voltage * 2.0
    percentage = int((battery_voltage - 3.6) * 100.0 / 0.6)
    percentage = max(0, min(100, percentage))
    return raw, adc_voltage * 1000.0, battery_voltage, percentage


def update_status_bar():
    global filtered_battery
    current = read_battery_info()[3]
    if filtered_battery is None:
        filtered_battery = current
    else:
        delta = current - filtered_battery
        if delta >= 2 or delta <= -2:
            filtered_battery = (filtered_battery * 3 + current) // 4
    ui.battery = filtered_battery


def refresh_battery_snapshot():
    global battery_info_snapshot
    info = read_battery_info()
    battery_info_snapshot = (info[0], info[1], info[2], info[3],
                             filtered_battery if filtered_battery is not None
                             else info[3])


def home_lines():
    device = unique_device_id()
    device_0 = int.from_bytes(device[:4], "big")
    device_1 = int.from_bytes(device[4:], "big")
    return ("T-Echo-Lite KeyShield  v1.0", "", "[Chip]",
            "model: nRF52840", "clock: 64MHz",
            "id: %08X-%08X" % (device_0, device_1), "", "[Memory]",
            "flash / ram: 1024 / 256KB", "", "[Software]",
            "name: general_test", "build: " + BUILD_TIME, "", "[Screen]",
            "type: SSD1681 EPD", "size: 192 x 176px", "", "[LVGL]",
            "version: v9.5.0")


def battery_lines():
    if battery_info_snapshot is None:
        return ("[Battery]", "press Center to refresh")
    raw, adc_mv, voltage, percentage, filtered = battery_info_snapshot
    return ("[Battery]", "level: %u%%" % percentage,
            "filtered: %u%%" % filtered, "voltage: %.3fV" % voltage, "",
            "[ADC]", "raw average: %u" % raw,
            "adc voltage: %.1fmV" % adc_mv, "samples: 16",
            "reference: 3000mV", "resolution: 4096", "", "[Calibration]",
            "divider: 2.00x", "empty: 3.60V", "full: 4.20V")


def bluetooth_lines():
    connected = bool(ble and ble.connected)
    ui.ble_connected = connected
    # ubluepy does not forward peer-name/RSSI/connection-update events to
    # Python. Show the fixed MTU and the initial link defaults configured by
    # this firmware; do not confuse the 20-byte ATT payload with the 27-byte
    # link-layer data length shown by the Arduino implementation.
    central_name = "Central" if connected else "unknown"
    rssi = "not exposed" if connected else "unknown"
    mtu = 23 if connected else 0
    data_length = 27 if connected else 0
    interval = "12.00ms" if connected else "unknown"
    phy = "1 Mbps" if connected else "unknown"
    return ("[Bluetooth]", "initialized: " + ("yes" if ble else "no"),
            "connected: " + ("yes" if connected else "no"),
            "advertising: " + ("no" if connected else ("yes" if ble else "no")),
            "", "[Device]", "name: T-Echo-Lite-KeyShield",
            "service: BLE UART", "", "[Central]",
            "name: " + central_name, "rssi: " + rssi,
            "mtu: %u" % mtu, "data length: %u" % data_length,
            "interval: " + interval, "phy: " + phy)


def ensure_audio():
    global codec, codec_failed
    if codec is not None:
        return codec
    if codec_failed:
        return None
    try:
        if ES8311_IIC_ADDRESS not in i2c.scan():
            print("es8311.Init fail")
            codec_failed = True
            return None
        from es8311 import ES8311
        codec = ES8311(i2c, ES8311_IIC_ADDRESS, ES8311_ADC_DATA,
                       ES8311_DAC_DATA, ES8311_WS_LRCK,
                       ES8311_BCLK, ES8311_MCLK)
        codec.begin(44100, 191, adc=True)
        return codec
    except (OSError, MemoryError):
        codec = None
        codec_failed = True
        print("es8311 config fail")
        return None


def audio_action():
    global audio_status, audio_action_running, record_available, last_action
    current_codec = ensure_audio()
    if current_codec is None:
        audio_status = "Audio codec not ready"
        refresh_current(update_battery=False)
        return
    if audio_target == 0:
        if not flash_ready:
            audio_status = "Flash not ready"
            refresh_current(update_battery=False)
            return
        audio_status = "Recording 3s..."
        audio_action_running = True
        refresh_current()
        try:
            def capture_complete():
                global audio_status, last_action
                audio_status = "Saving..."
                last_action = time.ticks_ms()
                try:
                    refresh_current(update_battery=False)
                except (MemoryError, OSError) as error:
                    print("Audio saving screen failed:", error)

            current_codec.stop()
            length = current_codec.record_file(AUDIO_RECORD_PATH,
                                               AUDIO_RECORD_MS,
                                               on_captured=capture_complete)
            record_available = (
                length > 0 and
                current_codec.recording_info(AUDIO_RECORD_PATH) is not None)
            print("Audio record: %u bytes, peak=%u, span=%u" % (
                length, current_codec.last_record_peak,
                current_codec.last_record_span))
            print("Audio capture: %u ms, stored=%u bytes, decimation=%u, max_refill=%u us" % (
                current_codec.last_record_elapsed_ms,
                current_codec.last_record_storage_bytes,
                current_codec.last_record_decimation,
                current_codec.last_record_refill_us))
            print("Audio save: %u ms" %
                  current_codec.last_record_save_elapsed_ms)
            audio_status = "Record complete" if record_available else "No audio"
        except MemoryError:
            record_available = False
            audio_status = "Record memory failed"
            print("Audio record failed: insufficient RAM")
        except OSError as error:
            record_available = False
            message = str(error)
            if "timeout" in message:
                audio_status = "Record I2S timeout"
            elif "RAM overrun" in message:
                audio_status = "Record I2S overrun"
            else:
                audio_status = "Flash write failed"
            print("Audio record failed:", error)
        finally:
            current_codec.stop()
            audio_action_running = False
            last_action = time.ticks_ms()
            # Release the three record DMA buffers before rendering or
            # starting the haptic completion indication.
            gc.collect()
            refresh_current(update_battery=False)
        if record_available:
            completion_vibration()
            last_action = time.ticks_ms()
    else:
        if not flash_ready:
            audio_status = "Flash not ready"
            refresh_current(update_battery=False)
            return
        if not record_available:
            audio_status = "No audio"
            refresh_current(update_battery=False)
            return
        audio_status = "Playing..."
        audio_action_running = True
        refresh_current()
        try:
            current_codec.stop()
            current_codec.play(AUDIO_RECORD_PATH)
            print("Audio play: %u ms, max_refill=%u us" % (
                current_codec.last_play_elapsed_ms,
                current_codec.last_play_refill_us))
            audio_status = "Play complete"
        except MemoryError:
            audio_status = "Play memory failed"
            print("Audio play failed: insufficient RAM")
        except OSError as error:
            audio_status = "Audio read failed"
            print("Audio play failed:", error)
        finally:
            current_codec.stop()
            audio_action_running = False
            last_action = time.ticks_ms()
            gc.collect()
            refresh_current(update_battery=False)
        if audio_status == "Play complete":
            completion_vibration()
            last_action = time.ticks_ms()


def _format_number(value, decimals):
    text = ("%.*f" % (decimals, value)).rstrip("0").rstrip(".")
    return text or "0"


def ensure_radio():
    global radio, radio_init_attempted, lora_next_send
    if radio is not None:
        return radio
    radio_init_attempted = True
    try:
        from example_helpers import make_radio
        radio = make_radio(lora_frequency, lora_bandwidth,
                           12, 8, 0x12, 22, 16, True)
        radio.start_receive()
        lora_next_send = time.ticks_add(time.ticks_ms(), LORA_AUTO_SEND_MS)
        log("SX1262 LoRa initialized")
    except OSError:
        radio = None
        log("SX1262 initialization failed, error=-1")
    return radio


def shutdown_radio():
    global radio, radio_init_attempted, lora_auto_send, lora_tx_counter
    if radio is not None:
        try:
            radio.sleep()
        except OSError:
            pass
        radio = None
        log("SX1262 LoRa shutdown")
    radio_init_attempted = False
    lora_auto_send = False
    lora_tx_counter = 0
    Pin(LED_1, Pin.OUT, value=1)
    Pin(LED_2, Pin.OUT, value=1)
    gc.collect()


def lora_set_frequency(value):
    global lora_frequency, lora_frequency_text
    lora_frequency = value
    if radio is not None:
        try:
            radio.set_frequency(value)
            radio.start_receive()
            log("SX1262 frequency set to %.3f MHz" % value)
        except OSError:
            log("SX1262 frequency setup failed, error=-1")
            return False
    lora_frequency_text = _format_number(lora_frequency, 3)
    return True


def lora_set_bandwidth(value):
    global lora_bandwidth, lora_bandwidth_text
    lora_bandwidth = min(LORA_BANDWIDTHS, key=lambda item: abs(item - value))
    if radio is not None:
        try:
            radio.configure(bandwidth=lora_bandwidth)
            radio.start_receive()
            log("SX1262 bandwidth set to %.2f kHz" % lora_bandwidth)
        except OSError:
            log("SX1262 bandwidth setup failed, error=-1")
            return False
    lora_bandwidth_text = _format_number(lora_bandwidth, 2)
    return True


def lora_toggle_auto():
    global lora_auto_send, lora_tx_counter, lora_next_send
    if radio is None and ensure_radio() is None:
        return
    lora_auto_send = not lora_auto_send
    lora_tx_counter = 0
    lora_next_send = time.ticks_add(time.ticks_ms(), LORA_AUTO_SEND_MS)


def lora_append(text, label):
    if len(label) == 1 and "0" <= label <= "9":
        return (text + label)[:LORA_TEXT_MAX]
    if label == "*":
        if "." not in text and len(text) < LORA_TEXT_MAX:
            return (text if text else "0") + "."
    elif label == "#":
        return text[:-1]
    elif label == "No":
        return ""
    return None


def handle_lora_key(label):
    global page_selected, lora_control, lora_frequency_text
    global lora_bandwidth_text, lora_frequency_editing
    global lora_bandwidth_editing
    if lora_frequency_editing:
        result = lora_append(lora_frequency_text, label)
        if result is not None:
            lora_frequency_text = result
        elif label in ("Center", "Yes"):
            try:
                value = float(lora_frequency_text)
                if 150.0 <= value <= 960.0:
                    lora_set_frequency(value)
                else:
                    lora_frequency_text = _format_number(lora_frequency, 3)
            except ValueError:
                lora_frequency_text = _format_number(lora_frequency, 3)
            lora_frequency_editing = False
        elif label == "Esc":
            lora_frequency_text = _format_number(lora_frequency, 3)
            lora_frequency_editing = False
        else:
            return False
        return True
    if lora_bandwidth_editing:
        result = lora_append(lora_bandwidth_text, label)
        if result is not None:
            lora_bandwidth_text = result
        elif label in ("Center", "Yes"):
            try:
                value = float(lora_bandwidth_text)
                if value > 0:
                    lora_set_bandwidth(value)
                else:
                    lora_bandwidth_text = _format_number(lora_bandwidth, 2)
            except ValueError:
                lora_bandwidth_text = _format_number(lora_bandwidth, 2)
            lora_bandwidth_editing = False
        elif label == "Esc":
            lora_bandwidth_text = _format_number(lora_bandwidth, 2)
            lora_bandwidth_editing = False
        else:
            return False
        return True
    if label == "Down" and radio is not None:
        lora_control = (lora_control + 1) % 3
    elif label == "Up" and radio is not None:
        lora_control = (lora_control - 1) % 3
    elif label == "Center":
        if radio is None:
            ensure_radio()
        elif lora_control == 0:
            lora_frequency_editing = True
            lora_frequency_text = ""
        elif lora_control == 1:
            lora_bandwidth_editing = True
            lora_bandwidth_text = ""
        else:
            lora_toggle_auto()
    elif label == "Yes":
        lora_control = 2
        lora_toggle_auto()
    elif label == "Esc":
        page_selected = False
        lora_control = 0
        lora_frequency_editing = False
        lora_bandwidth_editing = False
        lora_frequency_text = _format_number(lora_frequency, 3)
    else:
        return False
    return True


def _pulse_led(pin, receive=False):
    global lora_tx_led_deadline, lora_rx_led_deadline
    Pin(pin, Pin.OUT, value=0)
    deadline = time.ticks_add(time.ticks_ms(), 80)
    if receive:
        lora_rx_led_deadline = deadline
    else:
        lora_tx_led_deadline = deadline


def process_lora():
    global lora_rx_count, lora_rx_data, lora_rssi, lora_snr
    global lora_tx_counter, lora_next_send
    now = time.ticks_ms()
    if lora_tx_led_deadline and time.ticks_diff(now, lora_tx_led_deadline) >= 0:
        Pin(LED_1, Pin.OUT, value=1)
    if lora_rx_led_deadline and time.ticks_diff(now, lora_rx_led_deadline) >= 0:
        Pin(LED_2, Pin.OUT, value=1)
    if radio is None:
        return False
    changed = False
    try:
        if radio.poll():
            packet = radio.read()
            radio.start_receive()
            if packet is not None:
                lora_rx_count += 1
                lora_rssi = radio.last_rssi
                lora_snr = radio.last_snr
                if len(packet) >= 8 and packet[:4] == b"SXLT":
                    lora_rx_data = str(int.from_bytes(packet[4:8], "big"))
                elif not packet:
                    lora_rx_data = "empty"
                else:
                    lora_rx_data = "".join("%02X" % value for value in packet[:8])
                    if len(packet) > 8:
                        lora_rx_data += "..."
                _pulse_led(LED_2, True)
                log("SX1262 RX len=%u rssi=%.1f snr=%.1f" %
                    (len(packet), lora_rssi, lora_snr))
                changed = True
        if lora_auto_send and time.ticks_diff(now, lora_next_send) >= 0:
            packet = b"SXLT" + lora_tx_counter.to_bytes(4, "big")
            _pulse_led(LED_1)
            radio.transmit(packet)
            radio.start_receive()
            lora_tx_counter += 1
            lora_next_send = time.ticks_add(time.ticks_ms(), LORA_AUTO_SEND_MS)
    except OSError:
        pass
    return changed


def initialize_gps():
    global gps_uart, gps_parser, gps_enter_ms, gps_module_found
    global gps_wait_seconds
    from nmea import NMEA
    gps_parser = NMEA()
    gps_uart = setup_gps()
    gps_enter_ms = time.ticks_ms()
    gps_module_found = False
    gps_wait_seconds = -1


def shutdown_gps():
    global gps_uart, gps_parser, gps_module_found
    if gps_uart is not None and hasattr(gps_uart, "deinit"):
        gps_uart.deinit()
    Pin(GPS_RT9080_EN, Pin.OUT, value=0)
    gps_uart = None
    gps_parser = None
    gps_module_found = False
    gc.collect()


def process_gps():
    global gps_module_found, gps_wait_seconds
    if gps_uart is None:
        return False
    changed = False
    available = gps_uart.any() if hasattr(gps_uart, "any") else 0
    if available:
        data = gps_uart.read(min(available, 512))
        if data:
            if not gps_module_found and b"$G" in data:
                gps_module_found = True
                log("GPS module detected")
                changed = True
            if gps_parser.feed(data):
                changed = True
    waiting = time.ticks_diff(time.ticks_ms(), gps_enter_ms) // 1000
    if gps_module_found and not gps_parser.valid and waiting != gps_wait_seconds:
        gps_wait_seconds = waiting
        changed = True
    return changed


def initialize_imu():
    global imu, imu_found, imu_values
    imu_values = None
    if ICM20948_ADDRESS not in i2c.scan():
        imu = None
        imu_found = False
        log("IMU not found (I2C address NACK)")
        return
    try:
        from icm20948 import ICM20948
        imu = ICM20948(i2c, ICM20948_ADDRESS)
        imu.begin(calibrate=False)
        imu_found = True
        log("IMU ICM20948 initialized")
    except OSError:
        imu = None
        imu_found = False
        log("IMU ICM20948 init failed")


def read_imu():
    global imu_values
    if not imu_found or imu is None:
        return False
    try:
        pitch, roll, yaw, accel, gyro, mag, temperature = imu.orientation()
        imu_values = ("pitch: %6.1f deg" % pitch,
                      "roll:  %6.1f deg" % roll,
                      "yaw:   %6.1f deg" % yaw,
                      "temp:  %.1f C" % temperature)
        return True
    except OSError:
        return False


def shutdown_imu():
    global imu, imu_found, imu_values
    if imu is not None:
        try:
            imu.sleep(True)
        except OSError:
            pass
    imu = None
    imu_found = False
    imu_values = None
    gc.collect()


def select_page(new_page):
    global page, page_selected, battery_scroll, lora_control
    global lora_frequency_editing, lora_bandwidth_editing
    if page == new_page:
        return
    old_name = PAGES[page]
    new_name = PAGES[new_page]
    if old_name == "Audio" and codec is not None:
        codec.stop()
    if old_name == "LoRa":
        shutdown_radio()
        page_selected = False
    if old_name == "GPS":
        shutdown_gps()
    if old_name == "IMU":
        shutdown_imu()
    if new_name == "Battery":
        battery_scroll = 0
        update_status_bar()
        refresh_battery_snapshot()
    elif new_name == "LoRa":
        lora_control = 0
        lora_frequency_editing = False
        lora_bandwidth_editing = False
        ensure_radio()
    elif new_name == "GPS":
        initialize_gps()
    elif new_name == "IMU":
        initialize_imu()
    page = new_page


def _gps_screen():
    if gps_parser is None:
        ui.gps(page_selected, False, False)
        return
    has_fix = gps_parser.valid
    elapsed = max(0, time.ticks_diff(time.ticks_ms(), gps_enter_ms) // 1000)
    fix_text = None
    if gps_module_found:
        fix_text = ("time to fix: %u s" if has_fix else "waiting: %u s") % elapsed
    satellites = "sat: %u used / %u visible" % (
        gps_parser.satellites or 0, gps_parser.satellites_visible)
    cn0 = ("max cn0: %d dBHz" % gps_parser.max_cn0
           if gps_parser.max_cn0 > 0 else None)
    dop = None
    if has_fix:
        dop = "dop: h %.1f | v %.1f | p %.1f" % (
            gps_parser.hdop or 0.0,
            gps_parser.vdop or 0.0,
            gps_parser.pdop or 0.0)
    clock = None
    if gps_parser.utc and gps_parser.date:
        year, month, day = gps_parser.date
        hour, minute, second = gps_parser.utc
        second += gps_parser.utc_centisecond / 100.0
        clock = "time: %02u/%02u/%04u %02u:%02u:%05.2f" % (
            day, month, year, (hour + 8) % 24, minute, second)
    elif gps_module_found:
        clock = "time: waiting..."
    ui.gps(page_selected, gps_module_found, has_fix, fix_text,
           "lat: %.6f" % gps_parser.latitude if has_fix else None,
           "lon: %.6f" % gps_parser.longitude if has_fix else None,
           satellites if gps_module_found else None, cn0, dop,
           "speed: %.1f km/h" % (gps_parser.speed_kmph or 0.0)
           if has_fix else None, clock)


def refresh_current(update_battery=True):
    if update_battery:
        update_status_bar()
    name = PAGES[page]
    if name == "Home":
        ui.home(home_lines(), name, page_selected, home_scroll)
    elif name == "Keyboard":
        ui.text_list(keyboard_history, name, page_selected)
    elif name == "Audio":
        ui.audio(page_selected, audio_target == 0,
                 audio_status, audio_action_running)
    elif name == "Battery":
        ui.home(battery_lines(), name, page_selected, battery_scroll)
    elif name == "Bluetooth":
        ui.home(bluetooth_lines(), name, page_selected, bluetooth_scroll)
    elif name == "LoRa":
        if radio is None:
            ui.home(("[sx1262 lora]", "", "LoRa module init failed"),
                    name, page_selected)
        else:
            ui.lora(page_selected, lora_frequency_text, lora_bandwidth_text,
                    lora_auto_send, lora_rx_data,
                    "rssi: unknown" if lora_rssi is None else
                    "rssi: %.1fdBm" % lora_rssi,
                    "snr: unknown" if lora_snr is None else
                    "snr: %.1fdB" % lora_snr,
                    lora_control, lora_frequency_editing,
                    lora_bandwidth_editing)
    elif name == "GPS":
        _gps_screen()
    else:
        ui.imu(page_selected, imu_found, imu_values)


def handle_key(label):
    global page_selected, home_scroll, battery_scroll, bluetooth_scroll
    global last_action, audio_target, audio_status, keyboard_history
    last_action = time.ticks_ms()
    handled = False
    use_key_vibration = True
    if label == "Home":
        select_page(0)
        page_selected = False
        home_scroll = battery_scroll = 0
        handled = True
    elif not page_selected:
        if label == "Down":
            select_page((page + 1) % len(PAGES))
            handled = True
        elif label == "Up":
            select_page((page - 1) % len(PAGES))
            handled = True
        elif label == "Center":
            if PAGES[page] == "LoRa":
                ensure_radio()
            elif PAGES[page] == "IMU":
                read_imu()
            elif PAGES[page] == "Battery":
                update_status_bar()
                refresh_battery_snapshot()
                battery_scroll = 0
            page_selected = True
            handled = True
    elif PAGES[page] == "Home":
        if label == "Down":
            home_scroll = min(home_scroll + HOME_SCROLL_STEP,
                              max(0, len(home_lines()) - 10))
            handled = True
        elif label == "Up":
            home_scroll = max(0, home_scroll - HOME_SCROLL_STEP)
            handled = True
        elif label == "Esc":
            page_selected = False
            handled = True
    elif PAGES[page] == "Battery":
        if label == "Down":
            battery_scroll = min(battery_scroll + HOME_SCROLL_STEP,
                                 max(0, len(battery_lines()) - 10))
            handled = True
        elif label == "Up":
            battery_scroll = max(0, battery_scroll - HOME_SCROLL_STEP)
            handled = True
        elif label == "Esc":
            page_selected = False
            handled = True
        elif label == "Center":
            update_status_bar()
            refresh_battery_snapshot()
            battery_scroll = 0
            handled = True
    elif PAGES[page] == "Audio":
        if label in ("Down", "Up"):
            audio_target = 1 - audio_target
            audio_status = "Select Mic or Speaker"
            handled = True
        elif label == "Center":
            audio_action()
            # audio_action() refreshes both its running and final states.
            return
        elif label == "Esc":
            if codec is not None:
                codec.stop()
            audio_status = "Select Mic or Speaker"
            page_selected = False
            handled = True
    elif PAGES[page] == "Bluetooth":
        maximum = max(0, len(bluetooth_lines()) - 10)
        if label == "Down":
            bluetooth_scroll = min(bluetooth_scroll + HOME_SCROLL_STEP, maximum)
            handled = True
        elif label == "Up":
            bluetooth_scroll = max(0, bluetooth_scroll - HOME_SCROLL_STEP)
            handled = True
        elif label == "Center":
            handled = True
        elif label == "Esc":
            page_selected = False
            handled = True
    elif PAGES[page] == "LoRa":
        handled = handle_lora_key(label)
    elif PAGES[page] == "GPS":
        if label == "Esc":
            page_selected = False
            handled = True
    elif PAGES[page] == "IMU":
        if label == "Center":
            read_imu()
            handled = True
        elif label == "Esc":
            page_selected = False
            handled = True
    elif PAGES[page] == "Keyboard":
        if label == "Esc":
            page_selected = False
        else:
            if len(keyboard_history) >= 8:
                del keyboard_history[0]
            keyboard_history.append(label)
        handled = True
    if handled:
        if use_key_vibration:
            start_vibration()
        refresh_current()


def enter_light_sleep():
    global last_action, ble_status_changed
    log("Light sleep on")
    ui.sleeping = True
    ui.ble_connected = False
    refresh_current()
    if backlight is not None:
        try:
            backlight.off()
        except OSError:
            pass
    if ble is not None:
        try:
            ble.stop()
        except OSError:
            pass
    wake = [False]

    def wake_handler(pin):
        wake[0] = True

    boot = Pin(nRF52840_BOOT, Pin.IN, Pin.PULL_UP)
    boot.irq(trigger=Pin.IRQ_FALLING, handler=wake_handler)
    while not wake[0] and boot.value():
        sleep()
        time.sleep_ms(1000)
    boot.irq(handler=None)
    if ble is not None:
        try:
            ble.start()
        except OSError:
            pass
    log("Awakening")
    ui.sleeping = False
    ui.ble_connected = bool(ble and ble.connected)
    if backlight is not None:
        try:
            backlight.brightness(None, 4095)
        except OSError:
            pass
    ble_status_changed = False
    last_action = time.ticks_ms()
    refresh_current()


_init_keyboard()
_init_backlight(0)
_init_haptic()
ensure_audio()
_init_flash()
update_status_bar()
ui.boot()
_init_backlight(4095)
_init_ble()
print("ScreenRefreshTask start")
refresh_current()

while True:
    if keyboard is not None and not key_irq.value():
        try:
            events = keyboard.events()
        except OSError:
            print("parse_irq_status fail")
            events = ()
        for number, pressed, position, label in events:
            if pressed and label and label != "Null":
                handle_key(label)

    screen_changed = process_lora()
    process_ble()
    if process_gps():
        screen_changed = True
    if screen_changed and PAGES[page] in ("LoRa", "GPS"):
        refresh_current()

    if ble_status_changed:
        ble_status_changed = False
        refresh_current()

    now = time.ticks_ms()
    if PAGES[page] == "LoRa" and page_selected:
        last_action = now
    if (PAGES[page] not in ("LoRa", "GPS") and
            time.ticks_diff(now, last_action) > AUTO_SLEEP_MS):
        enter_light_sleep()
    time.sleep_ms(10)
