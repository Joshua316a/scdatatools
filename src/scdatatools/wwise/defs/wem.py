import ctypes

RIFF_SIGNATURE = b"RIFF"
RIFF_FORMAT = b"WAVE"
WEM_FMT = 0xFFFF
VORB_HDR = (
    b"\x30\x00\x00\x00\x02\x31\x00\x00\x00\xb6\x29\x02\xe6\x00\x00\x00\x41\x78\x4d\x01\x00\x00\x40\x03\xa8\x15"
    b"\x02\x00\x8e\x16\x02\x00\xcd\x02\x40\x03\x20\x4c\x00\x00\x10\x4e\x00\x00\xe6\xe0\xc5\x3f\x08\x0b"
)


class WemRiffHeader(ctypes.LittleEndianStructure):
    _fields_ = [
        ("id", ctypes.c_char * 4),
        ("size", ctypes.c_uint32),
        ("format", ctypes.c_char * 4),
    ]


class WemFormatHeader(ctypes.LittleEndianStructure):
    _fields_ = [
        ("id", ctypes.c_char * 4),
        ("size", ctypes.c_uint32),
        ("format", ctypes.c_uint16),
        ("channels", ctypes.c_uint16),
        ("sample_rate", ctypes.c_uint32),
        ("avg_bytes_per_sec", ctypes.c_uint32),
        ("block_align", ctypes.c_uint16),
        ("bits_per_sample", ctypes.c_uint16),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = b"fmt "
        self.extra_data = b""
