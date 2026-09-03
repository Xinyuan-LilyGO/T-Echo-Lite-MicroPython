"""PCM test signal generators for the ES8311 examples."""

import binascii
import hashlib
import math
import os
import struct

NOTIFICATION_NAME = "new_notification_010_c2_b16_s44100.raw"
NOTIFICATION_SIZE = 224386
NOTIFICATION_SHA256 = (
    b"f4837820281d5df424c5e3dc9aed271faa8c17ab3c2e57c760cc67b5cdf87bd5"
)
NOTIFICATION_CACHE = "/internal/" + NOTIFICATION_NAME
NOTIFICATION_TEMP = NOTIFICATION_CACHE + ".tmp"
NOTIFICATION_SOURCES = ("/flash/lib/" + NOTIFICATION_NAME,
                        "/flash/" + NOTIFICATION_NAME,
                        "/lib/" + NOTIFICATION_NAME,
                        NOTIFICATION_NAME)


def tone(frequency=1000, sample_rate=44100, duration_ms=100,
         amplitude=10000, square=False):
    samples = max(1, sample_rate * duration_ms // 1000)
    output = bytearray(samples * 4)
    for index in range(samples):
        phase = frequency * index / sample_rate
        if square:
            sample = amplitude if (phase % 1.0) < 0.5 else -amplitude
        else:
            sample = int(math.sin(phase * 2 * math.pi) * amplitude)
        struct.pack_into("<hh", output, index * 4, sample, sample)
    return output


def _file_size(path):
    try:
        return os.stat(path)[6]
    except OSError:
        return -1


def _sha256(path):
    digest = hashlib.sha256()
    block = bytearray(4096)
    with open(path, "rb") as source:
        while True:
            count = source.readinto(block)
            if not count:
                break
            digest.update(memoryview(block)[:count])
    return binascii.hexlify(digest.digest())


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _cache_notification(source_path):
    # Remove only files owned by this cache.  A stale full-size cache leaves
    # too little room for a second 224 KiB file on the 256 KiB filesystem.
    _remove(NOTIFICATION_TEMP)
    _remove(NOTIFICATION_CACHE)

    digest = hashlib.sha256()
    block = bytearray(4096)
    try:
        with open(source_path, "rb") as source:
            with open(NOTIFICATION_TEMP, "wb") as destination:
                while True:
                    count = source.readinto(block)
                    if not count:
                        break
                    data = memoryview(block)[:count]
                    destination.write(data)
                    digest.update(data)
        if (_file_size(NOTIFICATION_TEMP) != NOTIFICATION_SIZE or
                binascii.hexlify(digest.digest()) != NOTIFICATION_SHA256):
            raise OSError("Arduino notification PCM checksum mismatch")
        os.rename(NOTIFICATION_TEMP, NOTIFICATION_CACHE)
    except Exception:
        _remove(NOTIFICATION_TEMP)
        raise


def notification(sample_rate=44100):
    if sample_rate != 44100:
        raise ValueError("notification audio is recorded at 44100 Hz")

    # Arduino reads this array from nRF52840 internal Flash.  Cache the exact
    # same bytes in /internal so playback never accesses the external SPI Flash
    # that shares the ES8311 power rail.
    if (_file_size(NOTIFICATION_CACHE) == NOTIFICATION_SIZE and
            _sha256(NOTIFICATION_CACHE) == NOTIFICATION_SHA256):
        return NOTIFICATION_CACHE

    try:
        os.stat("/internal")
    except OSError:
        raise OSError("Internal filesystem /internal is not mounted")

    for path in NOTIFICATION_SOURCES:
        if _file_size(path) == NOTIFICATION_SIZE:
            _cache_notification(path)
            return NOTIFICATION_CACHE
    raise OSError("Missing exact Arduino PCM: " + NOTIFICATION_NAME)
