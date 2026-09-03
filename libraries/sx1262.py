"""SX1262 LoRa driver for the S62F module on T-Echo-Lite."""

from machine import Pin
import time


class SX1262:
    IRQ_TX_DONE = 0x0001
    IRQ_RX_DONE = 0x0002
    IRQ_TIMEOUT = 0x0200
    IRQ_CRC_ERROR = 0x0040
    BW_CODES = {7.8: 0x00, 10.4: 0x08, 15.6: 0x01, 20.8: 0x09,
                31.25: 0x02, 41.7: 0x0A, 62.5: 0x03, 125.0: 0x04,
                250.0: 0x05, 500.0: 0x06}

    def __init__(self, spi, cs, busy, reset, dio1, rf_vc1=None, rf_vc2=None):
        self.spi = spi
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.busy = Pin(busy, Pin.IN)
        self.reset_pin = Pin(reset, Pin.OUT, value=1)
        self.dio1 = Pin(dio1, Pin.IN)
        self.vc1 = Pin(rf_vc1, Pin.OUT, value=0) if rf_vc1 is not None else None
        self.vc2 = Pin(rf_vc2, Pin.OUT, value=1) if rf_vc2 is not None else None
        self.frequency = 868.0
        self.bandwidth = 125.0
        self.sf = 9
        self.cr = 6
        self.sync_word = 0xAB
        self.power = 22
        self.preamble = 16
        self.crc = False
        self.last_rssi = None
        self.last_snr = None
        self._sleeping = False

    def _wait_busy(self, timeout_ms=1000):
        start = time.ticks_ms()
        while self.busy.value():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("SX1262 BUSY timeout")

    def _write(self, opcode, data=b""):
        self._wait_busy()
        self.cs.off()
        self.spi.write(bytes((opcode,)))
        if data:
            self.spi.write(data)
        self.cs.on()
        self._wait_busy()

    def _write_without_busy_wait(self, opcode, data=b""):
        self.cs.off()
        self.spi.write(bytes((opcode,)))
        if data:
            self.spi.write(data)
        self.cs.on()

    def _read(self, opcode, command=b"", length=1):
        self._wait_busy()
        self.cs.off()
        self.spi.write(bytes((opcode,)) + command + b"\x00")
        result = self.spi.read(length, 0x00)
        self.cs.on()
        self._wait_busy()
        return result

    def reset(self):
        self.reset_pin.off()
        time.sleep_ms(2)
        self.reset_pin.on()
        time.sleep_ms(10)
        self._wait_busy()
        self._sleeping = False

    def begin(self, frequency=868.0, bandwidth=125.0, spreading_factor=9,
              coding_rate=6, sync_word=0xAB, power=22, preamble=16, crc=False):
        self.reset()
        self._write(0x80, b"\x00")
        self._write(0x96, b"\x01")
        self._write(0x97, b"\x06\x00\x01\x40")
        self._write(0x9D, b"\x00")
        self._write(0x8A, b"\x01")
        self._write(0x8F, b"\x00\x00")
        self._write(0x95, b"\x04\x07\x00\x01")
        self._write(0x8E, bytes((power & 0xFF, 0x04)))
        self.set_frequency(frequency)
        self.configure(bandwidth, spreading_factor, coding_rate, sync_word,
                       power, preamble, crc)
        self.clear_irq()
        return True

    def configure(self, bandwidth=None, spreading_factor=None, coding_rate=None,
                  sync_word=None, power=None, preamble=None, crc=None):
        if bandwidth is not None:
            self.bandwidth = float(bandwidth)
        if spreading_factor is not None:
            self.sf = int(spreading_factor)
        if coding_rate is not None:
            self.cr = int(coding_rate)
        if sync_word is not None:
            self.sync_word = int(sync_word)
        if power is not None:
            self.power = int(power)
            self._write(0x8E, bytes((self.power & 0xFF, 0x04)))
        if preamble is not None:
            self.preamble = int(preamble)
        if crc is not None:
            self.crc = bool(crc)
        bw = min(self.BW_CODES, key=lambda x: abs(x - self.bandwidth))
        symbol_ms = (1 << self.sf) / (bw * 1000.0) * 1000.0
        ldro = 1 if symbol_ms >= 16 else 0
        self._write(0x8B, bytes((self.sf, self.BW_CODES[bw], self.cr - 4, ldro)))
        self._write(0x8C, bytes((self.preamble >> 8, self.preamble & 0xFF,
                                0x00, 0xFF, 1 if self.crc else 0, 0x00)))
        # SX126x stores the 8-bit LoRa sync word as two nibbles with the
        # standard 0x44 control bits (the same mapping used by RadioLib).
        sync_msb = (self.sync_word & 0xF0) | 0x04
        sync_lsb = ((self.sync_word & 0x0F) << 4) | 0x04
        self.write_register(0x0740, bytes((sync_msb, sync_lsb)))

    def set_frequency(self, mhz):
        self.frequency = float(mhz)
        if self.frequency >= 900:
            calibration = b"\xE1\xE9"
        elif self.frequency >= 850:
            calibration = b"\xD7\xDB"
        elif self.frequency >= 779:
            calibration = b"\xC1\xC5"
        elif self.frequency >= 470:
            calibration = b"\x75\x81"
        else:
            calibration = b"\x6B\x6F"
        self._write(0x98, calibration)
        value = int(self.frequency * 1000000 * (1 << 25) / 32000000)
        self._write(0x86, value.to_bytes(4, "big"))

    def write_register(self, address, data):
        self._write(0x0D, bytes((address >> 8, address & 0xFF)) + data)

    def read_register(self, address, length=1):
        return self._read(0x1D, bytes((address >> 8, address & 0xFF)), length)

    def clear_irq(self, mask=0xFFFF):
        self._write(0x02, bytes((mask >> 8, mask & 0xFF)))

    def irq_status(self):
        data = self._read(0x12, b"", 2)
        return (data[0] << 8) | data[1]

    def _rf_switch(self, transmit):
        if self.vc1 is not None:
            self.vc1.value(1 if transmit else 0)
            self.vc2.value(0 if transmit else 1)

    def transmit(self, data, timeout_ms=10000):
        if isinstance(data, str):
            data = data.encode()
        if len(data) > 255:
            raise ValueError("LoRa packet too long")
        self._write(0x80, b"\x00")
        self._rf_switch(True)
        self._write(0x0E, b"\x00" + data)
        self._write(0x8C, bytes((self.preamble >> 8, self.preamble & 0xFF,
                                0x00, len(data), 1 if self.crc else 0, 0x00)))
        mask = self.IRQ_TX_DONE | self.IRQ_TIMEOUT
        self._write(0x08, bytes((mask >> 8, mask & 0xFF, mask >> 8,
                                mask & 0xFF, 0, 0, 0, 0)))
        self.clear_irq()
        ticks = min(0xFFFFFF, int(timeout_ms * 64))
        self._write(0x83, ticks.to_bytes(3, "big"))
        start = time.ticks_ms()
        while True:
            irq = self.irq_status()
            if irq & self.IRQ_TX_DONE:
                self.clear_irq(irq)
                self._rf_switch(False)
                return True
            if irq & self.IRQ_TIMEOUT or time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                self.clear_irq()
                self._rf_switch(False)
                return False
            time.sleep_ms(2)

    def start_receive(self, timeout_ms=0):
        self._rf_switch(False)
        self._write(0x8C, bytes((self.preamble >> 8, self.preamble & 0xFF,
                                0x00, 0xFF, 1 if self.crc else 0, 0x00)))
        mask = self.IRQ_RX_DONE | self.IRQ_TIMEOUT | self.IRQ_CRC_ERROR
        self._write(0x08, bytes((mask >> 8, mask & 0xFF, mask >> 8,
                                mask & 0xFF, 0, 0, 0, 0)))
        self.clear_irq()
        ticks = 0xFFFFFF if timeout_ms <= 0 else min(0xFFFFFF, int(timeout_ms * 64))
        self._write(0x82, ticks.to_bytes(3, "big"))

    def poll(self):
        irq = self.irq_status()
        return bool(irq & (self.IRQ_RX_DONE | self.IRQ_TIMEOUT | self.IRQ_CRC_ERROR))

    def read(self):
        irq = self.irq_status()
        if not irq & self.IRQ_RX_DONE or irq & self.IRQ_CRC_ERROR:
            self.clear_irq(irq)
            return None
        status = self._read(0x13, b"", 2)
        length, offset = status[0], status[1]
        data = self._read(0x1E, bytes((offset,)), length)
        packet = self._read(0x14, b"", 3)
        self.last_rssi = -packet[0] / 2.0
        snr = packet[1] - 256 if packet[1] & 0x80 else packet[1]
        self.last_snr = snr / 4.0
        self.clear_irq(irq)
        return data

    def receive(self, timeout_ms=10000):
        self.start_receive(timeout_ms)
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) <= timeout_ms:
            if self.poll():
                return self.read()
            time.sleep_ms(2)
        self.clear_irq()
        return None

    def continuous_wave(self):
        self._rf_switch(True)
        self.clear_irq()
        self._write(0xD1)

    def sleep(self):
        self._wait_busy()
        # SetSleep does not return to the normal BUSY-low command state.
        # RadioLib therefore sends it without a post-command BUSY wait.
        self._write_without_busy_wait(0x84, b"\x04")
        time.sleep_ms(1)
        self._sleeping = True

    def standby(self):
        if self._sleeping:
            # Pull NSS low with a NOP first. This wakes the radio before the
            # normal SetStandby command performs its BUSY handshakes.
            self._write_without_busy_wait(0x00)
        self._write(0x80, b"\x00")
        self._sleeping = False
