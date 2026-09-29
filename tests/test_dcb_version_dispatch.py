"""
tests/test_dcb_version_dispatch.py — Workstream 1, Phase 1 Tasks 1.2/1.3.

Synthetic minimal DCBs (hand-built header + records, all other tables empty)
verify version dispatch and the byte-budget assertion without game data:

- v5/v6 parse with byte-identical classic 32-byte records (Task 1.2).
- v8 and unknown versions refuse loudly, naming the version (Task 1.2).
- Truncated record tables raise DCBBudgetError, never struct.error or
  plausible garbage (Task 1.3).
"""

import ctypes
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conftest  # noqa: F401  (package stub bootstrap)

from scdatatools.forge import DataCoreBinary, dftypes


# ── Minimal DCB builder ─────────────────────────────────────────────────────

# Header field order per DataCoreHeader._fields_: 2×u32, 4×u16, 26×u32 with
# record_definition_count at u32 index 4.
_N_U32 = 26
_RECORD_COUNT_IDX = 4


def build_dcb(version: int, n_records: int, record_bytes: bytes | None = None):
    """Build a minimal DCB: full header, empty tables, N classic records."""
    counts = [0] * _N_U32
    counts[_RECORD_COUNT_IDX] = n_records
    header = struct.pack("<IIHHHH" + "I" * _N_U32, 0, version, 0, 0, 0, 0, *counts)
    assert len(header) == ctypes.sizeof(dftypes.DataCoreHeader)
    if record_bytes is None:
        record_bytes = b"".join(_record(i) for i in range(n_records))
    return header + record_bytes


def _record(idx=0):
    noparent = 0xFFFFFFFF
    guid = bytes([idx % 256]) + b"\x00" * 15  # distinct per record
    return struct.pack(
        "<III16sHH",
        0, 0, noparent, guid, 0xFFFF, 0xFFFF,
    )


# ── Task 1.2: version dispatch ──────────────────────────────────────────────

def test_v5_and_v6_share_classic_32_byte_records():
    assert ctypes.sizeof(dftypes.Record) == 32
    assert dftypes.record_type_for_version(5) is dftypes.Record
    assert dftypes.record_type_for_version(6) is dftypes.Record


def test_v5_parses_record_count():
    dcb = DataCoreBinary(build_dcb(5, 3))
    assert len(dcb.records) == 3
    assert len(dcb.records_by_guid) == 3


def test_v6_parses_record_count():
    dcb = DataCoreBinary(build_dcb(6, 2))
    assert len(dcb.records) == 2


def test_v8_refuses_loudly_naming_version():
    with pytest.raises(dftypes.DataCoreVersionError, match="8"):
        DataCoreBinary(build_dcb(8, 0))


def test_unknown_version_refuses_loudly_naming_version():
    with pytest.raises(dftypes.DataCoreVersionError, match="99"):
        DataCoreBinary(build_dcb(99, 0))


# ── Task 1.3: byte-budget assertion ─────────────────────────────────────────

def test_truncated_record_table_raises_budget_error():
    blob = build_dcb(5, 10, record_bytes=_record() * 2)  # claims 10, has 2
    with pytest.raises(dftypes.DCBBudgetError, match="records"):
        DataCoreBinary(blob)


def test_assert_byte_budget_ok_case_passes():
    dftypes.assert_byte_budget(3, 32, 96, "records")  # exact fit: no raise


def test_assert_byte_budget_message_carries_counts():
    with pytest.raises(dftypes.DCBBudgetError, match=r"10.*32.*64"):
        dftypes.assert_byte_budget(10, 32, 64, "records")
