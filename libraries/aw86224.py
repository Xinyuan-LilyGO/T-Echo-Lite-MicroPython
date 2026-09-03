"""AW86224 LRA haptic driver matching cpp_bus_driver's RAM mode."""

import binascii
import time


# Official HAPTIC_RAM_12K_041230_235 waveform library used by aw86224.ino.
# 711 bytes, base 0x0800, 4 sequences, SHA-256:
# 790e49ea43ed01bdc6204ceda3d7d5718be0c565cc40247ae880bf227a69c0d9
_RAM_HEX = (
    b"55081108e308e409be09bf0a930a940ac60102030406090d121a2635414b5156595c5e6061626363646465646462605d"
    b"585146382202e2ccbdb1a8a29d9895928f8c8a888785848485878b919aa8bcd8fb15283540474d53585c6164686c6f72"
    b"7476767674706a5f4f3818fdeadcd1c9c1bcb6b1aba6a19d98948f8c88858381818183868c93979c9fa3a7abafb3b7bb"
    b"c0c3c8cdd1d6dbe0e5eaf1f9031022394d5c676e7376797b7c7c7d7d7c7c7b7977736f685e4f3c2103e6ccb7a79b938e"
    b"8a878685858586888b8f959ea7b0b9c0c8cfd5dbe0e5e9eceff2f4f6f7f9fafbfcfdfdfe01020305070b10172130404c"
    b"555c6164676a6c6e6f717273747575757573716d675e503d2101ebdbcfc5bfb9b4afaba7a39f9b989592908f8e8f9196"
    b"9da9bad3ed000e19222930363c40464b51565b6064686a6c6d6c69635849321d0d01f7eee7e0d9d2cbc5bfb8b2aba59f"
    b"99948f8b878482818181828385888b8f93989da3a9afb5bbc0c6ccd2d8dee4ebf3fc08182d42535e666c707375767777"
    b"7777777674726f6b655c4f3e2710f9e4d2c3b8afa8a4a1a1a1a3a6a9adb1b5babfc2c7cbcfd3d7dbdee1e4e7eaeceef0"
    b"f2f3f5f6f7f8f9fafbfcfcfdfdfdfe0102030406090d131c28343c4145484b4c4e4f4f505151515151504f4d4a464037"
    b"2a16f9dbc5b7aca49e999592908d8b89888786858586898d939caabedcff1a2d3b444c52575c6063676a6d6f71737575"
    b"74726d665b4a3110f6e3d5cbc2bcb7b1aca8a39f9b97938f8c898684828181818386898b8e909395989c9fa3a6aaaeb2"
    b"b6babfc2c7ccd2d9e3ef0018334858626a6f7275777878797978787775736f6a6258493418fce1c9b7a79d95908d8b8a"
    b"89898a8c8f9399a1a9b0b8c0c5ccd2d7dce0e4e8ebedf0f2f4f5f7f8f9fafbfcfcfdfdfe00050a0e13171b1e21242627"
    b"282828262523201d1915110c0703fef9f4efebe7e3e0dddbdad9d8d8d9dadcdfe1e5e9edf1f6fb"
)
RAM_12K_041230_235 = binascii.unhexlify(_RAM_HEX)
del _RAM_HEX


class AW86224:
    LIBRARY_NAME = "12k_041230_235"
    LIBRARY_SAMPLE_RATE = 12000
    LIBRARY_RATED_F0_HZ = 235
    LIBRARY_WAVEFORM_COUNT = 4
    LIBRARY_BASE_ADDRESS = 0x0800
    RAM_WRITE_CHUNK_SIZE = 62

    def __init__(self, i2c, address=0x58):
        self.i2c = i2c
        self.address = address
        self._ram_loaded = False

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value & 0xFF,)))

    def _write_bytes(self, register, data):
        self.i2c.writeto_mem(self.address, register, data)

    def _read(self, register):
        return self.i2c.readfrom_mem(self.address, register, 1)[0]

    def _update(self, register, keep_mask, set_bits):
        self._write(register, (self._read(register) & keep_mask) | set_bits)

    def begin(self):
        if self.address not in self.i2c.scan():
            raise OSError("AW86224 not found")
        # Aw862xx::Init() only verifies that register 0 can be read.
        self._read(0x00)
        return True

    def software_reset(self):
        self._write(0x00, 0xAA)
        self._ram_loaded = False

    def get_f0_detection(self):
        # Exact Aw862xx::GetF0Detection() setup for the default 170.0 Hz
        # reference and 1000 mV LRA drive voltage.
        self.software_reset()
        self._write(0x5A, 0x00)
        self._update(0x08, 0xFC, 0x02)  # Continuous mode.
        self._update(0x18, 0xF7, 0x08)  # F0 detection on.
        self._update(0x1D, 0x7F, 0x80)  # Tracking on.
        self._update(0x08, 0xFB, 0x04)  # Auto brake on.
        self._update(0x1D, 0x80, 0x7F)
        self._update(0x1E, 0x80, 29)
        self._write(0x1F, 0x04)
        self._write(0x20, 0x14)
        self._write(0x22, 0x0F)
        self._write(0x1A, 0x6E)
        self._update(0x09, 0xFE, 0x01)
        time.sleep_ms(300)

        period = (self._read(0x25) << 8) | self._read(0x26)
        self._update(0x18, 0xF7, 0x00)
        self._update(0x08, 0xFB, 0x00)
        return 0 if period == 0 else 3840000 // period

    def input_voltage(self):
        self._update(0x43, 0xFF, 0x08)
        self._update(0x52, 0xFF, 0x02)
        time.sleep_ms(3)
        self._update(0x43, 0xF7, 0x00)
        code = (self._read(0x55) << 2) | ((self._read(0x57) & 0x30) >> 4)
        return 6.1 * code / 1024.0

    def _force_standby(self, enable):
        self._update(0x44, 0xBF, 0x40 if enable else 0x00)

    def stop_ram_playback(self):
        self._update(0x09, 0xFD, 0x02)
        self._force_standby(True)
        for _ in range(101):
            if (self._read(0x3F) & 0x0F) == 0:
                self._force_standby(False)
                return True
            time.sleep_ms(1)
        self._force_standby(False)
        raise OSError("AW86224 force standby timeout")

    def init_ram_mode(self):
        data = RAM_12K_041230_235
        if (len(data) != 711 or data[:17] !=
                b"\x55\x08\x11\x08\xe3\x08\xe4\x09\xbe\x09\xbf\x0a\x93\x0a\x94\x0a\xc6"):
            raise OSError("Invalid AW86224 RAM waveform library")

        self._update(0x44, 0xFC, 0x02)  # Official library is 12 kHz.
        self.stop_ram_playback()
        self._update(0x43, 0xF7, 0x08)  # RAMINIT on.
        time.sleep_us(500)

        base = self.LIBRARY_BASE_ADDRESS
        self._update(0x2D, 0xF0, (base >> 8) & 0x0F)
        self._write(0x2E, base & 0xFF)
        almost_empty = base >> 1
        almost_full = base - (base >> 2)
        thresholds = bytes((
            (((almost_empty >> 8) << 4) & 0xF0) |
            ((almost_full >> 8) & 0x0F),
            almost_empty & 0xFF,
            almost_full & 0xFF,
        ))
        self._write_bytes(0x2F, thresholds)
        self._write_bytes(0x40, bytes((base >> 8, base & 0xFF)))

        view = memoryview(data)
        offset = 0
        while offset < len(view):
            end = min(offset + self.RAM_WRITE_CHUNK_SIZE, len(view))
            self._write_bytes(0x42, view[offset:end])
            offset = end

        self._update(0x43, 0xF7, 0x00)  # RAMINIT off.
        self._ram_loaded = True
        return True

    def play_ram_waveform(self, sequence, loop_count=1, gain=255,
                          auto_brake=False, gain_bypass=True):
        if not self._ram_loaded:
            raise OSError("AW86224 RAM waveform library is not loaded")
        sequence = int(sequence)
        if sequence < 1 or sequence > self.LIBRARY_WAVEFORM_COUNT:
            raise ValueError("AW86224 waveform sequence out of range")
        loop_count = max(1, min(16, int(loop_count)))
        register_loop = loop_count - 1
        gain = max(0, min(255, int(gain)))

        self._write(0x0A, sequence)
        self._write(0x0B, 0x00)
        self._update(0x12, 0x0F, register_loop << 4)
        self._update(0x08, 0xFC, 0x00)  # RAM mode.
        self._update(0x08, 0xFB, 0x04 if auto_brake else 0x00)
        self._update(0x49, 0xBF, 0x40 if gain_bypass else 0x00)
        self._write(0x07, gain)
        self._update(0x09, 0xFE, 0x01)
        return True

    def play(self, frequency=235, duration_ms=120, gain=255):
        # Compatibility for general_test.py: Arduino uses sequence 1 once for
        # key feedback; frequency and duration were artifacts of the old RTP
        # implementation and never existed in the Arduino behavior.
        if int(frequency) != self.LIBRARY_RATED_F0_HZ:
            raise ValueError("only the official 235 Hz RAM library is loaded")
        if not self._ram_loaded:
            self.init_ram_mode()
        return self.play_ram_waveform(1, 1, gain, auto_brake=True)

    def stop(self):
        return self.stop_ram_playback()
