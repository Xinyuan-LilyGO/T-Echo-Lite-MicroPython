"""ES8311 codec setup plus direct nRF52840 I2S output."""

import time
from nrf_i2s import NRF52840I2S


class ES8311:
    def __init__(self, i2c, address, adc_data, dac_data, lrck, bclk, mclk):
        self.i2c = i2c
        self.address = address
        self.i2s = NRF52840I2S(dac_data, adc_data, lrck, bclk, mclk)

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value,)))

    def read_register(self, register):
        return self.i2c.readfrom_mem(self.address, register, 1)[0]

    def _update(self, register, keep_mask, set_bits):
        value = self.read_register(register)
        self._write(register, (value & keep_mask) | set_bits)

    def begin(self, sample_rate=44100, volume=191, adc=True):
        if self.address not in self.i2c.scan():
            raise OSError("ES8311 not found")
        self._write(0x00, 0x1F)
        time.sleep_ms(20)
        self._write(0x00, 0x00)
        self._write(0x00, 0x80)
        if (self.read_register(0xFD) << 8 | self.read_register(0xFE)) != 0x8311:
            raise OSError("ES8311 device ID mismatch")

        # cpp_bus_driver::Es8311::Init(): clock source, clocks and slave SDP.
        self._update(0x01, 0x7F, 0x00)
        self._update(0x01, 0x90, 0x2F)
        self._update(0x01, 0xE0, 0x1F)
        self._update(0x06, 0xDF, 0x00)
        self._update(0x00, 0xBB, 0x04)

        # SetClockCoeff(32, 44100), then 16-bit ADC and DAC SDP formats.
        self._update(0x02, 0x07, 0x18)
        self._write(0x03, 0x10)
        self._write(0x04, 0x10)
        self._write(0x05, 0x00)
        self._update(0x06, 0xE0, 0x03)
        self._update(0x07, 0xC0, 0x00)
        self._write(0x08, 0xFF)
        self._update(0x0A, 0xE3, 0x0C)
        self._update(0x09, 0xE3, 0x0C)

        # Arduino configures the nRF I2S peripheral before analog power paths.
        self.i2s.configure(sample_rate, 16)

        if adc:
            # Exact ConfigureEs8311() call order from es8311.ino.
            self._write(0x0D, 0x01)
            self._update(0x0E, 0xBF, 0x00)
            self._update(0x0E, 0xCF, 0x00)
            self._write(0x12, 0x00)
            self._write(0x13, 0x10)
            self._update(0x1C, 0xDF, 0x20)
            self._update(0x1C, 0xE0, 0x0A)
            self._update(0x37, 0xF7, 0x08)
            self._update(0x14, 0x8F, 0x10)
            self._update(0x18, 0x7F, 0x00)
            self._update(0x16, 0xF8, 0x03)
            self._update(0x14, 0xF0, 0x0A)
            self._write(0x17, 0xBF)
            # Match the reset-default AdcDataFormat::kAdcAdc used by the
            # Arduino driver: duplicate the mono ADC into both I2S slots.
            self._update(0x44, 0x8F, 0x00)
        else:
            # Exact speaker_certification.ino output-only power path.
            self._write(0x0D, 0x31)
            self._update(0x0E, 0xBF, 0x40)
            self._update(0x0E, 0xCF, 0x30)
            self._write(0x12, 0x00)
            self._write(0x13, 0x10)
            self._update(0x37, 0xF7, 0x08)

        self.set_dac_volume(volume)
        time.sleep_ms(20)
        return True

    def set_dac_volume(self, volume):
        self._write(0x32, max(0, min(255, int(volume))))

    def play(self, pcm, duration_ms=None):
        if hasattr(pcm, "play_i2s"):
            if duration_ms is not None:
                raise ValueError("duration_ms is not supported for generated audio")
            pcm.play_i2s(self.i2s)
            return
        if isinstance(pcm, str):
            if duration_ms is not None:
                raise ValueError("duration_ms is not supported for PCM files")
            self.i2s.play_file(pcm)
            return
        if len(pcm) & 3:
            raise ValueError("PCM buffer must contain 32-bit stereo words")
        self.i2s.loop(pcm, duration_ms)

    def record_file(self, path, duration_ms=3000, on_captured=None):
        return self.i2s.record_file(path, duration_ms,
                                    on_captured=on_captured)

    def recording_info(self, path):
        return self.i2s.recording_info(path)

    @property
    def last_record_peak(self):
        return self.i2s.last_record_peak

    @property
    def last_record_span(self):
        return self.i2s.last_record_span

    @property
    def last_record_words(self):
        return self.i2s.last_record_words

    @property
    def last_record_elapsed_ms(self):
        return self.i2s.last_record_elapsed_ms

    @property
    def last_record_storage_bytes(self):
        return self.i2s.last_record_storage_bytes

    @property
    def last_record_refill_us(self):
        return self.i2s.last_record_refill_us

    @property
    def last_record_decimation(self):
        return self.i2s.last_record_decimation

    @property
    def last_record_save_elapsed_ms(self):
        return self.i2s.last_record_save_elapsed_ms

    @property
    def last_play_elapsed_ms(self):
        return self.i2s.last_play_elapsed_ms

    @property
    def last_play_refill_us(self):
        return self.i2s.last_play_refill_us

    def stop(self):
        self.i2s.stop()
