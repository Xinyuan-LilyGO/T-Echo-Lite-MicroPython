"""Low-memory SSD1681 renderer matching general_test's LVGL layout."""

from binascii import unhexlify

from keyshield_font import FONT13, FONT14
from ssd1681 import SSD1681


# Exact U+E31D and U+E32D glyphs from the Arduino example's
# lvgl_font_material_symbols_rounded_32.c. LVGL packs each glyph continuously
# MSB first, so these stay compact and do not require loading a font module.
_MIC_ICON = unhexlify(
    b"01e000fe0073801c"
    b"e0073801ce007380"
    b"1ce0073801ce0073"
    b"801ce0e738f8fe7e"
    b"1e1dc00770038e01"
    b"c1e0f03ff807f800"
    b"30000c00030000c0"
    b"00"
)
_SPEAKER_ICON = unhexlify(
    b"7fffe7fffff0007f"
    b"0207f0f87f0f87f0"
    b"f87f0f87f0707f00"
    b"07f0007f0f87f1fc"
    b"7f3fe7f3fe7f78f7"
    b"f7077f7077f3067f"
    b"38e7f3fe7f1fc7f0"
    b"207f00077ffff7ff"
    b"fe"
)


class KeyShieldUI:
    WIDTH = 192
    HEIGHT = 176
    STATUS_HEIGHT = 20
    FOOTER_HEIGHT = 20
    CONTENT_TOP = 22
    SENSOR_TOP = 24
    LINE_HEIGHT = 13
    VISIBLE_LINES = 10
    MAX_PARTIAL_REFRESH = 10

    def __init__(self, display):
        self.display = display
        self.partial_count = 0
        self.base_ready = False
        self.battery = 0
        self.ble_connected = False
        self.sleeping = False

    @staticmethod
    def text_width(value, font=FONT13, size=1):
        glyphs = font[1]
        first = font[2]
        last = font[3]
        width = 0
        for character in str(value):
            code = ord(character)
            if first <= code <= last:
                width += glyphs[(code - first) * 7 + 4] * size
        return width

    def text(self, value, x, top, color=0, font=FONT13, size=1):
        # Google Sans 13/14 baselines are 11/12 pixels below the LVGL top.
        baseline = top + (11 if font is FONT13 else 12) * size
        return self.display.gfx_font_text(
            value, x, baseline, font, color, size, wrap=False)

    def centered_text(self, value, top, color=0, font=FONT13, size=1,
                      left=0, width=WIDTH):
        text_width = self.text_width(value, font, size)
        x = left + max(0, (width - text_width) // 2)
        self.text(value, x, top, color, font, size)

    def refresh(self):
        if self.partial_count >= self.MAX_PARTIAL_REFRESH:
            self.display.show(SSD1681.FAST_REFRESH)
            self.partial_count = 0
            self.base_ready = False
        if not self.base_ready:
            self.display.set_ram_value_base_map(SSD1681.FAST_REFRESH)
            self.base_ready = True
        self.display.show(SSD1681.PARTIAL_REFRESH)
        self.partial_count += 1

    def reset_refresh(self):
        self.partial_count = 0
        self.base_ready = False

    def prepare(self):
        self.display.fill(1)

    def _battery_icon(self, x, y):
        level = max(0, min(6, self.battery // 17))
        self.display.rect(x, y + 1, 14, 8, 0)
        self.display.fill_rect(x + 14, y + 3, 2, 4, 0)
        if level:
            self.display.fill_rect(x + 2, y + 3, level * 2, 4, 0)

    def _bluetooth_icon(self, x, y):
        # Same status information as the Material icon, in a 9x13 footprint.
        if self.ble_connected:
            self.display.line(x, y + 1, x + 7, y + 6, 0)
            self.display.line(x + 7, y + 6, x, y + 12, 0)
        self.display.line(x + 3, y, x + 3, y + 13, 0)
        self.display.line(x + 3, y, x + 8, y + 4, 0)
        self.display.line(x + 8, y + 4, x, y + 10, 0)
        self.display.line(x, y + 3, x + 8, y + 10, 0)
        self.display.line(x + 8, y + 10, x + 3, y + 13, 0)

    def status(self):
        self.display.hline(0, 19, self.WIDTH, 0)
        if self.sleeping:
            self.text("Zz", 6, 1, font=FONT14)
        percentage = "%u%%" % self.battery
        percentage_x = self.WIDTH - 6 - self.text_width(percentage, FONT14)
        self.text(percentage, percentage_x, 1, font=FONT14)
        battery_x = percentage_x - 20
        self._battery_icon(battery_x, 4)
        self._bluetooth_icon(battery_x - 17, 2)

    def footer(self, page_name, selected=False):
        x, y, width, height = 58, 158, 76, 17
        self.display.rect(x, y, width, height, 0, selected)
        color = 1 if selected else 0
        self.centered_text(page_name, 159, color, FONT14,
                           left=x + 2, width=width - 4)

    def frame(self, page_name, selected=False):
        self.prepare()
        self.status()
        self.footer(page_name, selected)

    def boot(self):
        self.prepare()
        self.centered_text("LILYGO", 55, font=FONT14, size=2)
        self.refresh()

    def _scrollbar(self, scroll, line_count):
        if line_count <= self.VISIBLE_LINES:
            return
        bar_top = self.CONTENT_TOP
        bar_height = self.HEIGHT - self.CONTENT_TOP - self.FOOTER_HEIGHT - 2
        max_scroll = line_count - self.VISIBLE_LINES
        thumb_height = max(12, bar_height * self.VISIBLE_LINES // line_count)
        thumb_y = bar_top + ((bar_height - thumb_height) * scroll // max_scroll)
        self.display.vline(self.WIDTH - 5, bar_top, bar_height, 0)
        self.display.fill_rect(self.WIDTH - 6, thumb_y, 3, thumb_height, 0)

    def home(self, lines, page_name, selected=False, scroll=0):
        self.frame(page_name, selected)
        if lines:
            scroll = min(max(0, scroll), max(0, len(lines) - 1))
        for index, line in enumerate(lines[scroll:scroll + self.VISIBLE_LINES]):
            self.text(line, 6, self.CONTENT_TOP + index * self.LINE_HEIGHT)
        self._scrollbar(scroll, len(lines))
        self.refresh()

    def _wrap(self, value, width):
        result = []
        line = ""
        for character in str(value):
            candidate = line + character
            if line and self.text_width(candidate) > width:
                result.append(line)
                line = character
            else:
                line = candidate
        result.append(line)
        return result

    def text_list(self, lines, page_name, selected=False):
        if not lines:
            self.centered("Please enter the text", page_name, selected)
            return
        self.frame(page_name, selected)
        y = 24
        for item in lines:
            for line in self._wrap("[" + item + "]", self.WIDTH - 12):
                if y + self.LINE_HEIGHT > 156:
                    break
                self.text(line, 6, y)
                y += self.LINE_HEIGHT
        self.refresh()

    def centered(self, message, page_name=None, selected=False):
        self.prepare()
        self.status()
        if page_name is not None:
            self.footer(page_name, selected)
        lines = str(message).split("\n")
        top = 88 - len(lines) * self.LINE_HEIGHT // 2
        for index, line in enumerate(lines):
            self.centered_text(line, top + index * self.LINE_HEIGHT,
                               left=8, width=self.WIDTH - 16)
        self.refresh()

    def _audio_glyph(self, bitmap, x, y, width, height, color):
        offset = 0
        bit_number = 0
        bits = 0
        for glyph_y in range(height):
            for glyph_x in range(width):
                if bit_number & 7 == 0:
                    bits = bitmap[offset]
                    offset += 1
                if bits & 0x80:
                    self.display.pixel(x + glyph_x, y + glyph_y, color)
                bits = (bits << 1) & 0xFF
                bit_number += 1

    def _mic_icon(self, x, y, color):
        # 32 px advance centered in the 56 px LVGL label, ofs_x=7, pad_top=14.
        self._audio_glyph(_MIC_ICON, x + 19, y + 14, 18, 25, color)

    def _speaker_icon(self, x, y, color):
        # 32 px advance centered in the 56 px LVGL label, ofs_x=6, pad_top=14.
        self._audio_glyph(_SPEAKER_ICON, x + 18, y + 14, 20, 26, color)

    def audio(self, selected, mic_selected, message, action_running=False):
        self.frame("Audio", selected)
        for x, label, active in ((30, "Mic", mic_selected),
                                 (106, "Speaker", not mic_selected)):
            highlight = selected and active and action_running
            if selected and active:
                self.display.rect(x - 4, 32, 64, 64, 0)
                self.display.rect(x - 3, 33, 62, 62, 0)
            self.display.rect(x, 36, 56, 56, 0, highlight)
            if label == "Mic":
                self._mic_icon(x, 36, 1 if highlight else 0)
            else:
                self._speaker_icon(x, 36, 1 if highlight else 0)
            self.centered_text(label, 100, left=x - 4, width=64)
        self.centered_text(message, 130, left=8, width=self.WIDTH - 16)
        self.refresh()

    def _selection(self, x, y, width, height, selected):
        if selected:
            self.display.rect(x, y, width, height, 0)
            self.display.rect(x + 1, y + 1, width - 2, height - 2, 0)

    def _input(self, value, x, y, selected, editing):
        self._selection(x - 3, y - 3, 52, 26, selected)
        self.display.rect(x, y, 46, 20, 0, editing)
        self.centered_text(value, y + 2, 1 if editing else 0, FONT14,
                           left=x + 2, width=42)

    def lora(self, selected, frequency, bandwidth, auto_send, rx_data,
             rssi, snr, control=0, frequency_editing=False,
             bandwidth_editing=False):
        self.frame("LoRa", selected)
        self.text("[sx1262 lora]", 6, 23)
        self.text("frequency:", 6, 40)
        self._input(str(frequency), 90, 36, selected and control == 0,
                    selected and frequency_editing)
        self.text("mhz", 144, 40)
        self.text("bandwidth:", 6, 66)
        self._input(str(bandwidth), 90, 62, selected and control == 1,
                    selected and bandwidth_editing)
        self.text("khz", 144, 66)
        self.text("auto send:", 6, 92)
        self._selection(87, 85, 40, 24, selected and control == 2)
        self.display.rect(90, 88, 34, 18, 0)
        knob_x = 108 if auto_send else 92
        self.display.fill_rect(knob_x, 90, 14, 14, 0)
        self.text("on" if auto_send else "off", 144, 92)
        self.text("[rx]", 6, 114)
        self.text("data:", 6, 129)
        self.text(str(rx_data)[:19], 43, 129)
        self.text(str(rssi), 6, 141)
        self.text(str(snr), 96, 141)
        self.refresh()

    def gps(self, selected, module_found, has_fix, fix_text=None,
            latitude=None, longitude=None, satellites=None, cn0=None,
            dop=None, speed=None, clock=None):
        self.frame("GPS", selected)
        y = self.SENSOR_TOP

        def add(line):
            nonlocal y
            if line is not None and y < 156:
                self.text(line, 6, y)
                y += self.LINE_HEIGHT

        add("[gps]")
        add(fix_text)
        y += 2
        if not module_found:
            add("GPS module not found")
        elif not has_fix:
            add("Waiting for fix...")
            add(satellites)
            add(clock)
        else:
            add(latitude)
            add(longitude)
            add(satellites)
            add(cn0)
            add(dop)
            add(speed)
            add(clock)
        self.refresh()

    def imu(self, selected, module_found, values=None):
        self.frame("IMU", selected)
        y = self.SENSOR_TOP
        self.text("[imu]", 6, y)
        y += self.LINE_HEIGHT + 2
        if not module_found:
            self.text("IMU module not found", 6, y)
        elif values:
            for line in values:
                self.text(line, 6, y)
                y += self.LINE_HEIGHT
            y += self.LINE_HEIGHT
            self.text("Press Center to refresh", 6, y)
        self.refresh()
