import time
from aw86224 import AW86224
from example_helpers import shared_i2c
from t_echo_lite_config import AW86224_IIC_ADDRESS, power_on

GAINS = (16, 32, 48, 64, 80, 96, 112, 128,
         144, 160, 176, 192, 208, 224, 240, 255)
LOOP_COUNT = 15
PLAY_MS = 220
STOP_MS = 180

print("Ciallo")
power_on(reset=True)
haptic = AW86224(shared_i2c(500000), AW86224_IIC_ADDRESS)
try:
    haptic.begin()
except OSError:
    print("Aw86224 init failed")

try:
    detected_f0 = haptic.get_f0_detection()
except OSError:
    detected_f0 = 0
if not detected_f0:
    print("Aw86224 F0 reference read failed")
else:
    print("Aw86224 F0 reference: %u.%uHz" %
          (detected_f0 // 10, detected_f0 % 10))

while True:
    try:
        haptic.init_ram_mode()
    except OSError:
        print("Aw86224 RAM waveform init failed")
        time.sleep_ms(1000)
        continue

    print("Aw86224 selected library: %s, sequences: %u, rated f0: %uHz" %
          (haptic.LIBRARY_NAME, haptic.LIBRARY_WAVEFORM_COUNT,
           haptic.LIBRARY_RATED_F0_HZ))
    print("Aw86224 gain test levels:" +
          "".join(" %u" % gain for gain in GAINS))
    print("Aw86224 GetInputVoltage: %.06f v" % haptic.input_voltage())

    for gain in GAINS:
        print("Aw86224 gain level: %u" % gain)
        for sequence in range(1, haptic.LIBRARY_WAVEFORM_COUNT + 1):
            print("Play %s sequence %u gain %u" %
                  (haptic.LIBRARY_NAME, sequence, gain))
            haptic.play_ram_waveform(sequence, LOOP_COUNT, gain)
            time.sleep_ms(PLAY_MS)
            haptic.stop_ram_playback()
            time.sleep_ms(STOP_MS)
    time.sleep_ms(1500)
