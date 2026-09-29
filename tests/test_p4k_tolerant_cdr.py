"""
tests/test_p4k_tolerant_cdr.py — Workstream 1, Phase 1 Task 1.1/1.4.

Hand-crafted minimal stored archives exercise the tolerant central-directory
walk without game data (no 155 GB Data.p4k needed):

- CIG-style custom extra tags (e.g. 0xCAFE) open instead of raising
  BadZipFile, and are recorded in the skipped-tags matrix.
- Unknown ZIP64 extra shapes record-and-continue (old code raised).
- Truncated extra tails record-and-stop instead of struct.error.
- The SC 4.7+ preamble path is covered (previously dead code).
- Structural: P4KFile._RealGetContents is a real method (not a nested
  closure), and _decodeExtra never raises BadZipFile.
"""

import ast
import io
import json
import os
import struct
import sys
import zlib

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conftest  # noqa: F401  (package stub bootstrap)

from scdatatools.p4k import P4KFile, P4KInfo


# ── Minimal stored-archive builder ──────────────────────────────────────────

def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_pack(entries, preamble=b""):
    """Build a minimal stored ZIP.

    entries: list of (filename: str, data: bytes, extra: bytes) where extra
        is the *central-directory* extra field (local extras are empty).
        All entries use method 0 (stored); see build_pack_methods() for
        compression-method coverage.
    preamble: when non-empty, reproduces the CIG layout the SC 4.7+ fix
        handles — the same garbage length is prepended before the local
        headers AND inside the central-directory window, while all stored
        offsets exclude it (so the parser must add it back via `concat`).
    Returns the full pack bytes.
    """
    return build_pack_methods([(fn, data, 0, extra) for fn, data, extra in entries],
                              preamble=preamble)


def build_pack_methods(entries, preamble=b""):
    """Build a minimal ZIP with per-entry compression methods.

    entries: list of (filename, data, method, extra). method 0 = stored;
        93 = zstd-deprecated, 100 = zstd, 101 = zlib-wrapped deflate.
        Payloads are encoded with the real codecs so read-back is a true
        round-trip. CRCs cover the uncompressed bytes.
    """
    import zlib

    out = io.BytesIO()
    out.write(preamble)
    central = io.BytesIO()
    for filename, data, method, extra in entries:
        fn = filename.encode("utf-8")
        if method == 0:
            payload = data
        elif method == 101:
            payload = zlib.compress(data)
        elif method in (93, 100):
            zstandard = pytest.importorskip("zstandard")
            payload = zstandard.compress(data)
        else:
            payload = data  # unknown methods: raw payload, open() must refuse
        # Stored offsets exclude the preamble, like real CIG packs.
        local_offset = out.tell() - len(preamble)
        out.write(struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50, 20, 0x0800, method, 0, 0,
            _crc(data), len(payload), len(data), len(fn), 0,
        ))
        out.write(fn)
        out.write(payload)
        central.write(struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50, 63, 20, 0x0800, method, 0, 0,
            _crc(data), len(payload), len(data), len(fn), len(extra), 0,
            0, 0, 0, local_offset,
        ))
        central.write(fn)
        central.write(extra)
    cd = preamble + central.getvalue()
    out.write(cd)
    # Stored central-directory offset is ABSOLUTE (it points at the preamble
    # itself) and the stored size covers preamble + entries; the walk derives
    # concat == 0 from these, then adds the preamble length back (concat fix).
    cd_offset = out.tell() - len(cd)
    cd_size = len(cd)
    count = len(entries)
    out.write(struct.pack(
        "<IHHHHIIH",
        0x06054B50, 0, 0, count, count, cd_size, cd_offset, 0,
    ))
    return out.getvalue()


def open_pack(tmp_path, payload: bytes, name="test.p4k"):
    path = os.path.join(str(tmp_path), name)
    with open(path, "wb") as f:
        f.write(payload)
    return P4KFile(path)


def tag(tp: int, data: bytes) -> bytes:
    return struct.pack("<HH", tp, len(data)) + data


# ── Task 1.1: tolerant walk ─────────────────────────────────────────────────

def test_custom_extra_tag_opens_and_is_recorded(tmp_path):
    payload = build_pack([(
        "Objects/test.cgf", b"CGF-DATA",
        tag(0xCAFE, b"CIG\x00\x01\x02"),  # CIG-style custom CDR tag
    )])
    pf = open_pack(tmp_path, payload)

    assert [i.filename for i in pf.filelist] == ["Objects/test.cgf"]
    assert pf.read("Objects/test.cgf") == b"CGF-DATA"
    matrix = pf.skipped_extra_tags
    assert 0xCAFE in matrix
    assert matrix[0xCAFE]["count"] == 1
    assert matrix[0xCAFE]["lengths"] == {6}
    assert matrix[0xCAFE]["files"] == ["Objects/test.cgf"]
    pf.close()


def test_unknown_zip64_shape_records_instead_of_raising(tmp_path):
    # 0x0001 with a length the old code rejected (old: BadZipFile).
    payload = build_pack([(
        "Objects/odd.cgf", b"X" * 64,
        struct.pack("<HH", 0x0001, 10) + b"\x00" * 10,
    )])
    pf = open_pack(tmp_path, payload)

    assert len(pf.filelist) == 1
    assert pf.read("Objects/odd.cgf") == b"X" * 64
    assert 0x0001 in pf.skipped_extra_tags
    pf.close()


def test_truncated_extra_tail_records_and_stops(tmp_path):
    extra = tag(0x0002, b"") + struct.pack("<HH", 0x9999, 50) + b"\x01\x02\x03"
    payload = build_pack([("Objects/trunc.cgf", b"DATA", extra)])
    pf = open_pack(tmp_path, payload)

    assert len(pf.filelist) == 1
    entry = pf.skipped_extra_tags[0x9999]
    assert entry["truncated"] is True
    pf.close()


def test_preamble_before_first_central_entry_is_skipped(tmp_path):
    payload = build_pack(
        [("Objects/a.cgf", b"A" * 16, b"")],
        preamble=b"CIG-PREAMBLE" + b"\x00" * 20,
    )
    pf = open_pack(tmp_path, payload)

    assert [i.filename for i in pf.filelist] == ["Objects/a.cgf"]
    assert pf.read("Objects/a.cgf") == b"A" * 16
    pf.close()


def test_plain_archive_has_empty_matrix(tmp_path):
    payload = build_pack([("Objects/plain.cgf", b"PLAIN", b"")])
    pf = open_pack(tmp_path, payload)

    assert len(pf.filelist) == 1
    assert pf.skipped_extra_tags == {}
    pf.close()


def test_skipped_tags_report_is_json_serialisable(tmp_path):
    payload = build_pack([
        ("Objects/a.cgf", b"A", tag(0xCAFE, b"1234")),
        ("Objects/b.cgf", b"B", tag(0xCAFE, b"12345678")),
    ])
    pf = open_pack(tmp_path, payload)

    report = pf.skipped_tags_report()
    json.dumps(report)  # must not raise
    assert report["0xcafe"]["count"] == 2
    assert report["0xcafe"]["lengths"] == [4, 8]
    pf.close()


# ── Structural: the walk is actually wired up ───────────────────────────────

def test_real_get_contents_is_a_class_method():
    import scdatatools.p4k as mod

    tree = ast.parse(open(mod.__file__).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "P4KFile":
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            assert "_RealGetContents" in methods
            return
    pytest.fail("P4KFile class not found")


def test_decode_extra_never_raises_bad_zip():
    import pathlib

    import scdatatools.p4k as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "P4KInfo":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_decodeExtra":
                    raises = [n for n in ast.walk(item) if isinstance(n, ast.Raise)]
                    assert raises == []
                    return
    pytest.fail("P4KInfo._decodeExtra not found")


# ── Task 3.2: compression methods registry ───────────────────────────────────

def test_method_101_zlib_deflate_roundtrip(tmp_path):
    payload = build_pack_methods([("Objects/z.cgf", b"ZLIB-DATA" * 100, 101, b"")])
    pf = open_pack(tmp_path, payload)
    assert pf.read("Objects/z.cgf") == b"ZLIB-DATA" * 100
    pf.close()


def test_method_93_zstd_deprecated_roundtrip(tmp_path):
    payload = build_pack_methods([("Objects/o.cgf", b"ZSTD93-DATA" * 100, 93, b"")])
    pf = open_pack(tmp_path, payload)
    assert pf.read("Objects/o.cgf") == b"ZSTD93-DATA" * 100
    pf.close()


def test_method_100_zstd_roundtrip(tmp_path):
    payload = build_pack_methods([("Objects/n.cgf", b"ZSTD100-DATA" * 100, 100, b"")])
    pf = open_pack(tmp_path, payload)
    assert pf.read("Objects/n.cgf") == b"ZSTD100-DATA" * 100
    pf.close()


def test_unknown_method_raises_naming_entry(tmp_path):
    payload = build_pack_methods([("Objects/mystery.cgf", b"???", 42, b"")])
    pf = open_pack(tmp_path, payload)
    with pytest.raises(ValueError, match="mystery.cgf"):
        pf.read("Objects/mystery.cgf")
    pf.close()


def test_methods_registry_unit():
    import zlib

    from scdatatools.p4k import decompressor_for_method

    assert isinstance(decompressor_for_method(100, "a")._decomp, object)
    assert isinstance(decompressor_for_method(93, "a")._decomp, object)
    assert isinstance(decompressor_for_method(101, "a"), zlib.decompressobj().__class__)
    with pytest.raises(ValueError, match="entry 'nope.cgf'"):
        decompressor_for_method(42, "nope.cgf")
