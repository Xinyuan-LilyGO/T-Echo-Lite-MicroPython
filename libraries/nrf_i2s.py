"""nRF52840 I2S EasyDMA transceiver using machine.mem32."""

import gc
import os
import struct
import time
import uctypes
import micropython
from machine import Pin, mem32


_AUDIO_MAGIC = b"TELA"
_AUDIO_VERSION = 1
_AUDIO_CODEC_PCM8 = 1
_AUDIO_DECIMATIONS = (2, 4)
_AUDIO_HEADER_FORMAT = "<4sBBBBIIIHHHH"
_AUDIO_HEADER_SIZE = struct.calcsize(_AUDIO_HEADER_FORMAT)
_AUDIO_PLAY_BLOCK_WORDS = 1373
_AUDIO_SAVE_BLOCK_BYTES = 4096


@micropython.viper
def _encode_pcm8(source: ptr8, target: ptr8, frame_count: int,
                 channel_offset: int, decimation: int, stats: ptr8) -> int:
    source_index = 0
    output_index = 0
    peak = int(stats[0]) | (int(stats[1]) << 8)
    minimum = (int(stats[2]) | (int(stats[3]) << 8)) - 32768
    maximum = (int(stats[4]) | (int(stats[5]) << 8)) - 32768

    while source_index < frame_count:
        sample_total = 0
        sample_count = 0
        group_index = 0
        while (group_index < decimation and
               source_index + group_index < frame_count):
            byte_index = ((source_index + group_index) * 4 +
                          channel_offset)
            sample = (int(source[byte_index]) |
                      (int(source[byte_index + 1]) << 8))
            if sample >= 32768:
                sample -= 65536
            sample_total += sample
            sample_count += 1
            group_index += 1

        sample = sample_total // sample_count

        absolute = sample
        if absolute < 0:
            absolute = -absolute
        if absolute > peak:
            peak = absolute
        if sample < minimum:
            minimum = sample
        if sample > maximum:
            maximum = sample

        quantized = (sample + 128) >> 8
        if quantized < -128:
            quantized = -128
        elif quantized > 127:
            quantized = 127
        target[output_index] = quantized + 128
        output_index += 1
        source_index += decimation

    stats[0] = peak & 255
    stats[1] = (peak >> 8) & 255
    minimum += 32768
    maximum += 32768
    stats[2] = minimum & 255
    stats[3] = (minimum >> 8) & 255
    stats[4] = maximum & 255
    stats[5] = (maximum >> 8) & 255
    return output_index


@micropython.viper
def _decode_pcm8(source: ptr8, source_count: int, target: ptr8,
                 target_frames: int, pending: int, repeat: int) -> int:
    source_index = 0
    frame_index = 0

    if pending >= 0:
        encoded = pending & 255
        repetitions = (pending >> 8) & 255
        high = encoded ^ 128
        while repetitions > 0 and frame_index < target_frames:
            byte_index = frame_index * 4
            target[byte_index] = 0
            target[byte_index + 1] = high
            target[byte_index + 2] = 0
            target[byte_index + 3] = high
            frame_index += 1
            repetitions -= 1
        if repetitions > 0:
            return encoded | (repetitions << 8)
        pending = -1

    while source_index < source_count and frame_index < target_frames:
        encoded = int(source[source_index])
        source_index += 1
        high = encoded ^ 128
        repetitions = repeat
        while repetitions > 0 and frame_index < target_frames:
            byte_index = frame_index * 4
            target[byte_index] = 0
            target[byte_index + 1] = high
            target[byte_index + 2] = 0
            target[byte_index + 3] = high
            frame_index += 1
            repetitions -= 1
        if repetitions > 0:
            pending = encoded | (repetitions << 8)

    return pending


@micropython.viper
def _zero_tail(target: ptr8, start: int, length: int):
    while start < length:
        target[start] = 0
        start += 1


def _parse_audio_header(data, file_size):
    if len(data) < 4 or data[:4] != _AUDIO_MAGIC:
        return None
    if len(data) != _AUDIO_HEADER_SIZE:
        raise ValueError("audio header truncated")
    fields = struct.unpack(_AUDIO_HEADER_FORMAT, data)
    if fields[1] != _AUDIO_VERSION or fields[2] != _AUDIO_CODEC_PCM8:
        raise ValueError("unsupported audio recording")
    channel = fields[3]
    decimation = fields[4]
    source_clock = fields[5]
    source_frames = fields[6]
    payload_bytes = fields[7]
    if channel > 1 or decimation not in _AUDIO_DECIMATIONS:
        raise ValueError("invalid audio format")
    if (source_clock != NRF52840I2S._SOURCE_CLOCK_HZ or
            fields[8] != NRF52840I2S._MCK_DIVIDER or
            fields[9] != NRF52840I2S._MCK_RATIO):
        raise ValueError("audio clock mismatch")
    if source_frames <= 0:
        raise ValueError("invalid audio length")
    expected_payload = (source_frames + decimation - 1) // decimation
    if payload_bytes != expected_payload:
        raise ValueError("invalid audio payload length")
    if file_size != _AUDIO_HEADER_SIZE + payload_bytes:
        raise ValueError("audio file truncated")
    return fields


class NRF52840I2S:
    BASE = 0x40025000
    TASKS_START = BASE + 0x000
    TASKS_STOP = BASE + 0x004
    EVENTS_STOPPED = BASE + 0x108
    EVENTS_RXPTRUPD = BASE + 0x104
    EVENTS_TXPTRUPD = BASE + 0x114
    ENABLE = BASE + 0x500
    CONFIG_MODE = BASE + 0x504
    CONFIG_RXEN = BASE + 0x508
    CONFIG_TXEN = BASE + 0x50C
    CONFIG_MCKEN = BASE + 0x510
    CONFIG_MCKFREQ = BASE + 0x514
    CONFIG_RATIO = BASE + 0x518
    CONFIG_SWIDTH = BASE + 0x51C
    CONFIG_ALIGN = BASE + 0x520
    CONFIG_FORMAT = BASE + 0x524
    CONFIG_CHANNELS = BASE + 0x528
    RXD_PTR = BASE + 0x538
    TXD_PTR = BASE + 0x540
    RXTXD_MAXCNT = BASE + 0x550
    PSEL_MCK = BASE + 0x560
    PSEL_SCK = BASE + 0x564
    PSEL_LRCK = BASE + 0x568
    PSEL_SDIN = BASE + 0x56C
    PSEL_SDOUT = BASE + 0x570
    _STOP_FIX_1 = BASE + 0x038
    _STOP_FIX_2 = BASE + 0x03C
    _SOURCE_CLOCK_HZ = 32000000
    _MCK_DIVIDER = 23
    _MCK_RATIO = 32
    _EFFECTIVE_SAMPLE_RATE = 43478

    def __init__(self, sdout, sdin, lrck, sck, mck):
        self.sdout = sdout
        self.sdin = sdin
        self.lrck = lrck
        self.sck = sck
        self.mck = mck
        self.buffer = None
        self.running = False
        self.sample_rate = 44100
        self.last_record_peak = 0
        self.last_record_span = 0
        self.last_record_words = 0
        self.last_record_elapsed_ms = 0
        self.last_record_storage_bytes = 0
        self.last_record_refill_us = 0
        self.last_record_decimation = 0
        self.last_record_save_elapsed_ms = 0
        self.last_play_elapsed_ms = 0
        self.last_play_refill_us = 0

    @staticmethod
    def _clear_event(address):
        mem32[address] = 0
        # Nordic's HAL reads an event back after clearing it.  This matters on
        # Cortex-M4 because peripheral writes can otherwise still be pending.
        _ = mem32[address]

    def configure(self, sample_rate=44100, bits=16):
        mem32[self.ENABLE] = 0
        self._pin_mck = Pin(self.mck, Pin.OUT, value=0)
        self._pin_sck = Pin(self.sck, Pin.OUT, value=0)
        self._pin_lrck = Pin(self.lrck, Pin.OUT, value=0)
        self._pin_sdout = Pin(self.sdout, Pin.OUT, value=0)
        self._pin_sdin = Pin(self.sdin, Pin.IN)
        mem32[self.PSEL_MCK] = self.mck
        mem32[self.PSEL_SCK] = self.sck
        mem32[self.PSEL_LRCK] = self.lrck
        mem32[self.PSEL_SDOUT] = self.sdout
        mem32[self.PSEL_SDIN] = self.sdin
        mem32[self.CONFIG_MODE] = 0
        mem32[self.CONFIG_RXEN] = 0
        mem32[self.CONFIG_TXEN] = 0
        mem32[self.CONFIG_MCKEN] = 1
        if sample_rate != 44100:
            raise ValueError("only 44100 Hz is supported")
        self.sample_rate = sample_rate
        # 32 MHz / 23 / 32 = 43.478 kHz, closest nRF divider to 44.1 kHz.
        mem32[self.CONFIG_MCKFREQ] = 0x0B000000
        mem32[self.CONFIG_RATIO] = 0  # 32x MCK/LRCK.
        mem32[self.CONFIG_SWIDTH] = 1 if bits == 16 else 0
        mem32[self.CONFIG_ALIGN] = 0
        mem32[self.CONFIG_FORMAT] = 0
        mem32[self.CONFIG_CHANNELS] = 0
        # Arduino leaves I2S disabled until StartTransmitI2s().
        mem32[self.ENABLE] = 0

    def start(self, buffer):
        if len(buffer) == 0 or len(buffer) & 3:
            raise ValueError("I2S buffer must contain complete 32-bit words")
        if len(buffer) // 4 > 0x3FFF:
            raise ValueError("I2S buffer exceeds EasyDMA MAXCNT")
        address = uctypes.addressof(buffer)
        if address & 3:
            raise ValueError("I2S buffer must be 32-bit aligned")
        self.buffer = buffer
        mem32[self.RXTXD_MAXCNT] = len(buffer) // 4
        mem32[self.CONFIG_RXEN] = 0
        mem32[self.CONFIG_TXEN] = 1
        self._clear_event(self.EVENTS_STOPPED)
        mem32[self.ENABLE] = 1
        # Enabling I2S can create a spurious TXPTRUPD event on nRF52
        # (anomaly 55).  Clear it after ENABLE, then install the first buffer.
        self._clear_event(self.EVENTS_TXPTRUPD)
        mem32[self.TXD_PTR] = address
        mem32[self.TASKS_START] = 1
        self.running = True

    def needs_buffer(self):
        return bool(mem32[self.EVENTS_TXPTRUPD])

    def _start_receive(self, buffer):
        if len(buffer) == 0 or len(buffer) & 3:
            raise ValueError("I2S buffer must contain complete 32-bit words")
        if len(buffer) // 4 > 0x3FFF:
            raise ValueError("I2S buffer exceeds EasyDMA MAXCNT")
        address = uctypes.addressof(buffer)
        if address & 3:
            raise ValueError("I2S buffer must be 32-bit aligned")
        self.buffer = buffer
        mem32[self.RXTXD_MAXCNT] = len(buffer) // 4
        mem32[self.CONFIG_TXEN] = 0
        mem32[self.CONFIG_RXEN] = 1
        self._clear_event(self.EVENTS_STOPPED)
        mem32[self.ENABLE] = 1
        # Enabling I2S can create a spurious RXPTRUPD event on nRF52
        # (anomaly 55). Clear it before installing the initial RX pointer.
        self._clear_event(self.EVENTS_RXPTRUPD)
        mem32[self.RXD_PTR] = address
        mem32[self.TASKS_START] = 1
        self.running = True

    def _queue_receive(self, buffer):
        address = uctypes.addressof(buffer)
        if address & 3:
            raise ValueError("I2S buffer must be 32-bit aligned")
        mem32[self.RXD_PTR] = address
        self._clear_event(self.EVENTS_RXPTRUPD)

    def _wait_receive_buffer(self, timeout_ms=1000):
        start = time.ticks_ms()
        while not mem32[self.EVENTS_RXPTRUPD]:
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError(
                    "I2S record timeout (enable=%u rxen=%u ptr=0x%08X)" % (
                        mem32[self.ENABLE], mem32[self.CONFIG_RXEN],
                        mem32[self.RXD_PTR]))
            time.sleep_ms(1)

    def record_file(self, path, duration_ms=3000, chunk_words=1024,
                    on_captured=None):
        """Capture exact-duration audio to RAM, then save it to LittleFS.

        Flash writes never run while EasyDMA is receiving.  The preferred
        format is unsigned PCM8 at half rate.  If the heap cannot hold that
        recording, allocation falls back to quarter rate instead of failing.
        """
        chunk_words = min(0x3FFC, int(chunk_words)) & ~3
        if chunk_words < 256:
            raise ValueError("invalid I2S chunk size")
        initial_chunk_words = chunk_words
        duration_ms = int(duration_ms)
        if duration_ms <= 0:
            raise ValueError("invalid I2S record duration")

        frame_denominator = self._MCK_DIVIDER * self._MCK_RATIO * 1000
        target_frames = (
            self._SOURCE_CLOCK_HZ * duration_ms + frame_denominator // 2
        ) // frame_denominator
        logical_bytes = target_frames * 4

        gc.collect()
        buffers = None
        payload_blocks = None
        stats = None
        decimation = _AUDIO_DECIMATIONS[0]
        while buffers is None:
            chunk_bytes = chunk_words * 4
            try:
                buffers = (bytearray(chunk_bytes), bytearray(chunk_bytes),
                           bytearray(chunk_bytes))
                payload_blocks = []
                remaining = target_frames
                while remaining > 0:
                    frame_count = min(chunk_words, remaining)
                    payload_blocks.append(bytearray(
                        (frame_count + decimation - 1) // decimation))
                    remaining -= frame_count
                # peak=0, minimum=32767, maximum=-32768, little-endian.
                stats = bytearray((0, 0, 255, 255, 0, 0))
            except MemoryError:
                buffers = None
                payload_blocks = None
                stats = None
                gc.collect()
                if chunk_words > 256:
                    chunk_words = max(256, (chunk_words // 2) & ~3)
                elif decimation == _AUDIO_DECIMATIONS[0]:
                    decimation = _AUDIO_DECIMATIONS[1]
                    chunk_words = initial_chunk_words
                else:
                    raise

        payload_bytes = (target_frames + decimation - 1) // decimation
        captured_frames = 0
        max_refill_us = 0
        capture_elapsed_ms = 0
        self.last_record_peak = 0
        self.last_record_span = 0
        self.last_record_words = 0
        self.last_record_elapsed_ms = 0
        self.last_record_storage_bytes = 0
        self.last_record_refill_us = 0
        self.last_record_decimation = 0
        self.last_record_save_elapsed_ms = 0

        # A three-buffer pipeline can absorb one isolated stall approaching two
        # block periods.  Compare against the absolute DMA schedule so smaller
        # stalls cannot accumulate until a pointer update is missed.
        block_period_us = (
            chunk_words * self._MCK_DIVIDER * self._MCK_RATIO * 1000000 //
            self._SOURCE_CLOCK_HZ
        )

        capture_started = time.ticks_ms()
        stream_started_us = time.ticks_us()
        processed_blocks = 0
        gc.disable()
        try:
            self._start_receive(buffers[0])
            self._wait_receive_buffer()
            self._queue_receive(buffers[1])
            playing = 0
            queued = 1
            spare = 2
            while captured_frames < target_frames:
                self._wait_receive_buffer()
                valid_frames = min(
                    chunk_words, target_frames - captured_frames)
                final_block = (
                    captured_frames + valid_frames >= target_frames)
                if final_block:
                    capture_elapsed_ms = time.ticks_diff(
                        time.ticks_ms(), capture_started)
                    self.stop()
                else:
                    self._queue_receive(buffers[spare])

                encoded = payload_blocks[processed_blocks]
                refill_started = time.ticks_us()
                encoded_count = _encode_pcm8(
                    buffers[playing], encoded, valid_frames, 0,
                    decimation, stats)
                refill_us = time.ticks_diff(
                    time.ticks_us(), refill_started)
                if refill_us > max_refill_us:
                    max_refill_us = refill_us
                if encoded_count != len(encoded):
                    raise OSError("I2S record encoding length mismatch")

                captured_frames += valid_frames
                processed_blocks += 1
                if not final_block:
                    absolute_deadline_us = (
                        (processed_blocks + 2) * block_period_us - 3000)
                    elapsed_us = time.ticks_diff(
                        time.ticks_us(), stream_started_us)
                    if elapsed_us >= absolute_deadline_us:
                        raise OSError("I2S record RAM overrun")
                    playing, queued, spare = queued, spare, playing
        finally:
            self.stop()
            gc.enable()

        peak = stats[0] | (stats[1] << 8)
        minimum = (stats[2] | (stats[3] << 8)) - 32768
        maximum = (stats[4] | (stats[5] << 8)) - 32768
        span = maximum - minimum
        header = struct.pack(
            _AUDIO_HEADER_FORMAT, _AUDIO_MAGIC, _AUDIO_VERSION,
            _AUDIO_CODEC_PCM8, 0, decimation,
            self._SOURCE_CLOCK_HZ, target_frames, payload_bytes,
            self._MCK_DIVIDER, self._MCK_RATIO, peak, span)

        # EasyDMA has released all three buffers.  Reclaim them before the
        # display callback and filesystem save, while retaining captured PCM.
        buffers = None
        self.buffer = None
        gc.collect()
        if on_captured is not None:
            on_captured()

        save_started = time.ticks_ms()
        with open(path, "wb") as output:
            write_output = output.write
            result = write_output(header)
            if result is not None and result != _AUDIO_HEADER_SIZE:
                raise OSError("audio header short write")

            save_buffer = bytearray(_AUDIO_SAVE_BLOCK_BYTES)
            save_view = memoryview(save_buffer)
            save_count = 0
            for block_index in range(len(payload_blocks)):
                block = payload_blocks[block_index]
                block_view = memoryview(block)
                block_offset = 0
                while block_offset < len(block):
                    copy_count = min(
                        len(block) - block_offset,
                        _AUDIO_SAVE_BLOCK_BYTES - save_count)
                    save_view[save_count:save_count + copy_count] = (
                        block_view[block_offset:block_offset + copy_count])
                    save_count += copy_count
                    block_offset += copy_count
                    if save_count == _AUDIO_SAVE_BLOCK_BYTES:
                        result = write_output(save_buffer)
                        if (result is not None and
                                result != _AUDIO_SAVE_BLOCK_BYTES):
                            raise OSError("audio payload short write")
                        save_count = 0
                payload_blocks[block_index] = None

            if save_count:
                result = write_output(save_view[:save_count])
                if result is not None and result != save_count:
                    raise OSError("audio payload short write")
            output.flush()
        save_elapsed_ms = time.ticks_diff(time.ticks_ms(), save_started)

        self.last_record_peak = peak
        self.last_record_span = span
        self.last_record_words = target_frames
        self.last_record_elapsed_ms = capture_elapsed_ms
        self.last_record_storage_bytes = _AUDIO_HEADER_SIZE + payload_bytes
        self.last_record_refill_us = max_refill_us
        self.last_record_decimation = decimation
        self.last_record_save_elapsed_ms = save_elapsed_ms
        return logical_bytes

    def queue(self, buffer):
        if len(buffer) != mem32[self.RXTXD_MAXCNT] * 4:
            raise ValueError("queued I2S buffer size must match MAXCNT")
        address = uctypes.addressof(buffer)
        if address & 3:
            raise ValueError("I2S buffer must be 32-bit aligned")
        self.buffer = buffer
        # Match nrf_i2s_tx_buffer_set() followed by nrf_i2s_event_clear().
        # Clearing first can let EasyDMA latch the old pointer again.
        mem32[self.TXD_PTR] = address
        self._clear_event(self.EVENTS_TXPTRUPD)

    def _wait_buffer(self, timeout_ms=1000):
        start = time.ticks_ms()
        while not self.needs_buffer():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise OSError("I2S buffer timeout")
            time.sleep_ms(1)

    def play_once(self, pcm, chunk_words=1024):
        if len(pcm) == 0 or len(pcm) & 3:
            raise ValueError("PCM data must contain complete 32-bit stereo words")
        source = memoryview(pcm)
        offset = 0

        def fill_from_memory(target):
            nonlocal offset
            count = min(len(target), len(source) - offset)
            if count:
                target[:count] = source[offset:offset + count]
                offset += count
            return count

        self.play_filler(fill_from_memory, chunk_words)

    def play_filler(self, filler, chunk_words=1024):
        chunk_bytes = min(0x3FFF, int(chunk_words)) * 4
        if chunk_bytes <= 0:
            raise ValueError("invalid I2S chunk size")
        gc.collect()
        # Three buffers keep one block playing, one queued in EasyDMA, and one
        # ready in Python.  File I/O therefore never sits between TXPTRUPD and
        # installing the next pointer.
        buffers = None
        while buffers is None:
            try:
                buffers = (bytearray(chunk_bytes), bytearray(chunk_bytes),
                           bytearray(chunk_bytes))
            except MemoryError:
                # A completed recording leaves enough total RAM but can split
                # the heap into regions smaller than one DMA block. Keep the
                # three-buffer pipeline and reduce only the contiguous block.
                buffers = None
                gc.collect()
                if chunk_bytes <= 1024:
                    raise
                chunk_bytes = max(1024, (chunk_bytes // 2) & ~3)

        def fill(target):
            count = filler(target) or 0
            if count < 0 or count > len(target):
                raise ValueError("invalid PCM filler result")
            if count < len(target):
                _zero_tail(target, count, len(target))
            return count

        self.last_play_elapsed_ms = 0
        self.last_play_refill_us = 0
        counts = [fill(buffers[0]), fill(buffers[1]), fill(buffers[2])]
        if not counts[0]:
            return

        playing = 0
        queued = 1
        ready = 2
        # Use the absolute DMA schedule.  This preserves the triple buffer's
        # tolerance for one isolated stall while rejecting cumulative lag that
        # would otherwise replay a stale block.
        block_period_us = (
            (chunk_bytes // 4) * self._MCK_DIVIDER * self._MCK_RATIO *
            1000000 // self._SOURCE_CLOCK_HZ
        )

        max_refill_us = 0
        play_started = 0
        stream_started_us = 0
        processed_refills = 0
        try:
            stream_started_us = time.ticks_us()
            self.start(buffers[playing])
            play_started = time.ticks_ms()
            # Initial START latches buffer 0.  Queue buffer 1 immediately.
            self._wait_buffer()
            self.queue(buffers[queued])

            while True:
                # The queued block has just started.  Submit the already-filled
                # ready block before doing any filesystem work.
                self._wait_buffer()
                released = playing
                playing = queued

                # A zero block follows the final padded PCM block.  Reaching
                # this boundary proves all source samples were transmitted.
                if not counts[playing]:
                    return

                self.queue(buffers[ready])
                queued = ready
                ready = released

                refill_started = time.ticks_us()
                counts[ready] = fill(buffers[ready])
                refill_us = time.ticks_diff(
                    time.ticks_us(), refill_started)
                if refill_us > max_refill_us:
                    max_refill_us = refill_us
                processed_refills += 1
                absolute_deadline_us = (
                    (processed_refills + 2) * block_period_us - 2000)
                elapsed_us = time.ticks_diff(
                    time.ticks_us(), stream_started_us)
                if elapsed_us >= absolute_deadline_us:
                    raise OSError("I2S source underrun")
        finally:
            self.stop()
            if play_started:
                self.last_play_elapsed_ms = time.ticks_diff(
                    time.ticks_ms(), play_started)
            self.last_play_refill_us = max_refill_us

    def recording_info(self, path):
        """Return logical/stored recording details, or None if invalid."""
        try:
            file_size = os.stat(path)[6]
            with open(path, "rb") as source:
                header = source.read(_AUDIO_HEADER_SIZE)
            fields = _parse_audio_header(header, file_size)
        except (OSError, ValueError, IndexError):
            return None
        if fields is None:
            return None
        return (fields[6] * 4, fields[7], fields[10], fields[11])

    def _play_compact_stream(self, source, fields):
        remaining_frames = fields[6]
        remaining_payload = fields[7]
        decimation = fields[4]
        pending = -1
        encoded = bytearray(
            (_AUDIO_PLAY_BLOCK_WORDS + decimation - 1) // decimation)

        def fill_compact(target):
            nonlocal remaining_frames, remaining_payload, pending
            if remaining_frames <= 0:
                if remaining_payload:
                    raise OSError("audio payload length mismatch")
                return 0

            frame_count = min(len(target) // 4, remaining_frames)
            prefix_frames = ((pending >> 8) & 255) if pending >= 0 else 0
            encoded_count = (
                frame_count - prefix_frames + decimation - 1) // decimation
            if encoded_count < 0 or encoded_count > remaining_payload:
                raise OSError("audio payload length mismatch")
            count = source.readinto(encoded, encoded_count)
            if count != encoded_count:
                raise OSError("audio file truncated")

            pending = _decode_pcm8(
                encoded, encoded_count, target, frame_count, pending,
                decimation)
            remaining_frames -= frame_count
            remaining_payload -= encoded_count
            if remaining_frames == 0 and remaining_payload:
                raise OSError("audio payload length mismatch")
            return frame_count * 4

        self.play_filler(fill_compact, _AUDIO_PLAY_BLOCK_WORDS)

    def play_file(self, path, chunk_words=1024):
        file_size = os.stat(path)[6]
        with open(path, "rb") as source:
            header = source.read(_AUDIO_HEADER_SIZE)
            try:
                fields = _parse_audio_header(header, file_size)
            except ValueError as error:
                raise OSError(str(error))
            if fields is not None:
                self._play_compact_stream(source, fields)
                return
            if path.endswith(".tela"):
                raise OSError("invalid audio recording")
            source.seek(0)
            self.play_filler(source.readinto, chunk_words)

    def loop(self, buffer, duration_ms=None):
        if duration_ms is None:
            self.play_once(buffer)
            return
        self.start(buffer)
        start = time.ticks_ms()
        while duration_ms is None or time.ticks_diff(time.ticks_ms(), start) < duration_ms:
            if self.needs_buffer():
                self.queue(buffer)
            time.sleep_ms(1)
        self.stop()

    def stop(self):
        if self.running:
            self._clear_event(self.EVENTS_STOPPED)
            mem32[self.TASKS_STOP] = 1
            # nRF52840 anomaly 194: STOP does not release every I2S resource.
            mem32[self._STOP_FIX_1] = 1
            mem32[self._STOP_FIX_2] = 1
            started = time.ticks_ms()
            while not mem32[self.EVENTS_STOPPED]:
                if time.ticks_diff(time.ticks_ms(), started) > 100:
                    break
                time.sleep_ms(1)
            mem32[self.ENABLE] = 0
            mem32[self.CONFIG_RXEN] = 0
            mem32[self.CONFIG_TXEN] = 0
            self.running = False
        # EasyDMA no longer owns the RAM after ENABLE is cleared. Drop the
        # last buffer reference so a completed recording cannot permanently
        # pin a DMA block and starve the following playback allocation.
        self.buffer = None
