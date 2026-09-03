"""TCA8418 keypad controller driver."""


class TCA8418:
    REG_CFG = 0x01
    REG_INT_STAT = 0x02
    REG_KEY_LCK_EC = 0x03
    REG_KEY_EVENT_A = 0x04
    REG_KP_GPIO1 = 0x1D
    REG_KP_GPIO2 = 0x1E
    REG_KP_GPIO3 = 0x1F

    def __init__(self, i2c, address=0x34, keymap=None):
        self.i2c = i2c
        self.address = address
        self.keymap = keymap

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value,)))

    def _read(self, register, length=1):
        return self.i2c.readfrom_mem(self.address, register, length)

    def begin(self, rows=5, columns=4):
        if self.address not in self.i2c.scan():
            raise OSError("TCA8418 not found")
        self._write(self.REG_KP_GPIO1, (1 << rows) - 1)
        self._write(self.REG_KP_GPIO2, (1 << columns) - 1)
        self._write(self.REG_KP_GPIO3, 0)
        self._write(self.REG_CFG, 0x11)  # KE_IEN and pulse interrupt mode.
        self.clear_fifo()
        self._write(self.REG_INT_STAT, 0x1F)
        return True

    def clear_fifo(self):
        count = self._read(self.REG_KEY_LCK_EC)[0] & 0x0F
        if count:
            self._read(self.REG_KEY_EVENT_A, count)

    def events(self):
        status = self._read(self.REG_INT_STAT)[0]
        count = self._read(self.REG_KEY_LCK_EC)[0] & 0x0F
        result = []
        for raw in self._read(self.REG_KEY_EVENT_A, count) if count else ():
            number = raw & 0x7F
            pressed = bool(raw & 0x80)
            position = ((number - 1) % 10, (number - 1) // 10)
            label = None
            if self.keymap is not None and 0 < number <= len(self.keymap):
                label = self.keymap[number - 1]
            result.append((number, pressed, position, label))
        if status:
            self._write(self.REG_INT_STAT, status)
        return result

