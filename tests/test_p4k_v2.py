"""
tests/test_p4k_v2.py — Workstream 1, Phase 1 Task 3.1 (JiJi v2 reader).

Hand-built minimal JiJi v2 packs (fixed 0xCC entries + name table + 175-byte
trailer) verify detection, the entry walk, and payload reads without game
data or external binaries. A svarog-generated v2 pack round-trips
identically (verified manually against /tmp/v2fix/v1.p4k).
"""

import os
import struct
import sys
import zlib

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conftest  # noqa: F401  (package stub bootstrap)

from scdatatools.p4k import (
    JIJI_CDR_ENTRY_SIZE,
    JIJI_EOCD_SIZE,
    JIJI_MAGIC,
    JIJI_VERSION,
    P4KFile,
)


def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_v2(entries):
    """Build a minimal JiJi v2 pack.

    entries: list of (filename, data, method) with method 0 (stored).
    Layout: payloads, entry array, name table, 175-byte trailer.
    """
    out = bytearray()
    meta = []
    for filename, data, method in entries:
        assert method == 0, "synthetic v2 builder covers stored entries"
        meta.append((filename, len(out), len(data)))
        out += data
    cd_off = len(out)
    name_table = bytearray()
    blobs = []
    for filename, data_off, size in meta:
        fn = filename.encode("utf-8")
        blobs.append(struct.pack(
            "<HHHIQQQQ",
            0, 0, 0, _crc(out[data_off:data_off + size]),
            size, size, data_off, len(name_table),
        ))
        blobs.append(b"\x00" * 128)  # signature
        blobs.append(struct.pack("<H", 0))  # encryption_flag
        blobs.append(b"\x00" * 32)  # sha256
        name_table += fn + b"\x00"
    out += b"".join(blobs)
    text_off = len(out)
    out += bytes(name_table)
    trailer = struct.pack(
        "<QQQQQQQQQQQQQB64sHI",
        len(entries), 0, cd_off, len(b"".join(blobs)), 0,
        text_off, len(name_table), 0, len(out), 0, 0, 0, 4096,
        0, b"\x00" * 64, JIJI_VERSION, JIJI_MAGIC,
    )
    assert len(trailer) == JIJI_EOCD_SIZE
    out += trailer
    return bytes(out)


def open_pack(tmp_path, payload: bytes, name="test_v2.p4k"):
    path = os.path.join(str(tmp_path), name)
    with open(path, "wb") as f:
        f.write(payload)
    return P4KFile(path)


# ── Task 3.1 ────────────────────────────────────────────────────────────────

def test_jiji_constants_match_oracle():
    assert JIJI_EOCD_SIZE == 0xAF
    assert JIJI_MAGIC == 0x696A694A
    assert JIJI_VERSION == 2
    assert JIJI_CDR_ENTRY_SIZE == 0xCC


def test_v2_detection_and_walk(tmp_path):
    pf = open_pack(tmp_path, build_v2([("a.txt", b"HELLO", 0)]))
    assert pf._pack_version == 2
    assert [i.filename for i in pf.filelist] == ["a.txt"]
    assert pf.read("a.txt") == b"HELLO"
    pf.close()


def test_v2_multiple_entries_with_nested_names(tmp_path):
    payload = build_v2([
        ("Docs/read me.txt", b"SPACED", 0),
        ("sub/dir/b.bin", b"\x00\x01\x02", 0),
    ])
    pf = open_pack(tmp_path, payload)
    assert sorted(i.filename for i in pf.filelist) == [
        "Docs/read me.txt", "sub/dir/b.bin",
    ]
    assert pf.read("Docs/read me.txt") == b"SPACED"
    assert pf.read("sub/dir/b.bin") == b"\x00\x01\x02"
    assert not any(getattr(i, "_p4k_v2", False) is False for i in pf.filelist)
    pf.close()


def test_v1_packs_still_take_v1_walk(tmp_path):
    from test_p4k_tolerant_cdr import build_pack

    pf = open_pack(
        tmp_path,
        build_pack([("Objects/plain.cgf", b"PLAIN", b"")]),
        name="plain_v1.p4k",
    )
    assert pf._pack_version == 1
    assert pf.read("Objects/plain.cgf") == b"PLAIN"
    pf.close()


def test_truncated_v2_central_directory_raises(tmp_path):
    good = build_v2([("a.txt", b"HELLO", 0)])
    # Corrupt the trailer's entry count upward: 50 claimed, 1 present.
    trailer = bytearray(good[-175:])
    struct.pack_into("<Q", trailer, 0, 50)
    with pytest.raises(Exception):
        open_pack(tmp_path, good[:-175] + bytes(trailer))
