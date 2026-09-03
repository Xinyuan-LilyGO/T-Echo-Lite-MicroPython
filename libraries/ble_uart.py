"""Nordic UART Service adapter for the nRF port's optional ubluepy module."""


class BleUnavailable(RuntimeError):
    pass


class BleUart:
    NOTIFY_PAYLOAD_SIZE = 20

    def __init__(self, name="T-Echo-Lite-nRF52840", on_receive=None,
                 on_connect=None, on_disconnect=None):
        try:
            from ubluepy import Service, Characteristic, UUID, Peripheral, constants
        except ImportError:
            raise BleUnavailable(
                "This firmware has no ubluepy/bluetooth module. Pure Python cannot "
                "provide a BLE controller; rebuild the nRF port with SoftDevice s140."
            )
        self.constants = constants
        self.on_receive = on_receive
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.connected = False
        self.notifications_enabled = False
        self.connection_handle = None
        service = Service(UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e"))
        self.rx = Characteristic(
            UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e"),
            props=Characteristic.PROP_WRITE | Characteristic.PROP_WRITE_WO_RESP)
        self.tx = Characteristic(
            UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e"),
            props=Characteristic.PROP_NOTIFY, attrs=Characteristic.ATTR_CCCD)
        service.addCharacteristic(self.rx)
        service.addCharacteristic(self.tx)
        self.peripheral = Peripheral()
        self.peripheral.addService(service)
        self.peripheral.setConnectionHandler(self._event)
        self.rx_handle = self.rx.getHandle()
        # The CCCD is the descriptor immediately following the TX value.
        self.tx_cccd_handle = self.tx.getHandle() + 1
        self.name = name
        self.service = service

    def _event(self, event, handle, data):
        if event == self.constants.EVT_GAP_CONNECTED:
            self.connected = True
            self.notifications_enabled = False
            self.connection_handle = handle
            if self.on_connect:
                self.on_connect(handle)
        elif event == self.constants.EVT_GAP_DISCONNECTED:
            self.connected = False
            self.notifications_enabled = False
            self.connection_handle = None
            reason = data[0] if data else 0
            if self.on_disconnect:
                self.on_disconnect(handle, reason)
            self.start()
        elif event == self.constants.EVT_GATTS_WRITE:
            if handle == self.tx_cccd_handle:
                self.notifications_enabled = bool(data and (data[0] & 0x01))
            elif self.on_receive and handle == self.rx_handle:
                self.on_receive(bytes(data))

    def start(self):
        # This ubluepy port only supports one 31-byte legacy advertising
        # packet and has no scan-response API. The original 20-byte name,
        # flags and 128-bit NUS UUID need 43 bytes together. Keep the original
        # visible name and omit only the UUID from the advertising packet; the
        # NUS service is still registered and discoverable after connecting.
        if len(self.name.encode("utf-8")) > 8:
            self.peripheral.advertise(device_name=self.name)
        else:
            self.peripheral.advertise(
                device_name=self.name, services=[self.service])

    def stop(self):
        """Stop advertising, matching Bluefruit.Advertising.stop()."""
        self.peripheral.advertise_stop()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        if not self.connected or not self.notifications_enabled:
            return False

        # ubluepy does not fragment notifications. With the default ATT MTU
        # of 23 bytes, each notification can carry at most 20 data bytes.
        # Splitting here matches the stream behavior of Arduino BLEUart.print().
        for offset in range(0, len(data), self.NOTIFY_PAYLOAD_SIZE):
            if not self.connected or not self.notifications_enabled:
                return False
            chunk = data[offset:offset + self.NOTIFY_PAYLOAD_SIZE]
            self.tx.write(bytearray(chunk))
        return True
