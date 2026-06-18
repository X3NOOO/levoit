from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, ChoicesSetting

# Philips / MUJI (Versuni) air-purifier UART. Frame layout:
#   FE FF | cmd(LE16) | len(1) | data[len] | checksum(LE16)
CMD_TYPES = {
    0x0001: "HS1",      # handshake / ack at boot
    0x0002: "HS2",      # handshake / ack at boot
    0x0003: "SET",      # module -> MCU: write a datapoint
    0x0004: "QUERY",    # module -> MCU: read a datapoint group
    0x0007: "STATUS",   # MCU -> module: status report (datapoint TLVs)
}


def crc16_ccitt_false(data):
    """CRC-16/CCITT-FALSE over the data payload; sent big-endian on the wire."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


class PhilipsExtractor(HighLevelAnalyzer):
    supported_analyzers = ["Async Serial"]
    channel = ChoicesSetting(label="Channel", choices=("module->MCU", "MCU->module", "-"))
    include_raw_bytes = ChoicesSetting(label="Include Raw Bytes", choices=("No", "Yes"))
    result_types = {"packet": {"format": "{{data.text}}"}}

    def __init__(self):
        self.reset()

    def reset(self):
        self.waiting = True
        self.bytes = []
        self.expected_length = None
        self.start_time = None
        self.end_time = None

    def decode(self, frame):
        try:
            return self._decode(frame)
        except Exception as e:
            return AnalyzerFrame("packet", frame.start_time, frame.end_time, {"text": f"ERR: {e}"})

    def _decode(self, frame):
        if frame.type not in ("data", "byte"):
            return None

        byte = frame.data["data"][0]

        # Look for the start of a frame: 0xFE
        if self.waiting:
            if byte == 0xFE:
                self.waiting = False
                self.bytes = [byte]
                self.start_time = frame.start_time
                self.end_time = frame.end_time
            return None

        # Second sync byte must be 0xFF, else resynchronise.
        if len(self.bytes) == 1:
            if byte == 0xFF:
                self.bytes.append(byte)
                self.end_time = frame.end_time
            elif byte == 0xFE:
                self.start_time = frame.start_time
                self.end_time = frame.end_time
            else:
                self.reset()
            return None

        self.bytes.append(byte)
        self.end_time = frame.end_time

        # Once the length byte (index 4) arrives, the full frame size is known:
        # FE FF (2) + cmd (2) + len (1) + data (len) + crc (2)
        if len(self.bytes) == 5:
            self.expected_length = 7 + self.bytes[4]

        if (self.expected_length and len(self.bytes) >= self.expected_length) or len(self.bytes) > 512:
            result = self.emit_frame()
            self.reset()
            return result

        return None

    def emit_frame(self):
        if self.start_time is None or len(self.bytes) < 7:
            return None

        b = self.bytes
        cmd = b[2] | (b[3] << 8)
        length = b[4]
        data = b[5:5 + length]
        crc = b[5 + length:5 + length + 2]

        label = CMD_TYPES.get(cmd, "UNK")
        data_str = " ".join(f"{x:02X}" for x in data)
        crc_str = " ".join(f"{x:02X}" for x in crc)

        # Verify CRC-16/CCITT-FALSE over the data payload (big-endian on wire)
        calc = crc16_ccitt_false(bytes(data))
        crc_ok = len(crc) == 2 and crc[0] == ((calc >> 8) & 0xFF) and crc[1] == (calc & 0xFF)
        crc_flag = "" if crc_ok else " !CRC"

        # Friendly hint for the query group (data = <group> 00)
        extra = ""
        if cmd == 0x0004 and len(data) >= 1:
            extra = f"  GROUP={data[0]:02X}"

        raw_str = " ".join(f"{x:02X}" for x in b)
        raw = f"  |  RAW={raw_str}" if self.include_raw_bytes == "Yes" else ""
        ch = f"[{self.channel}] " if self.channel and self.channel != "-" else ""
        text = f"{ch}{label}(0x{cmd:04X}){extra}  |  LEN={length}  |  DATA={data_str}  |  CRC={crc_str}{crc_flag}{raw}"

        return AnalyzerFrame("packet", self.start_time, self.end_time, {"text": text})
