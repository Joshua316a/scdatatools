Version Matrix
==============

Pack and DataCore format coverage of the native readers (Workstream 1).
Statuses: ✅ native support · ⚠️ best-effort · ❌ unsupported.
“Evidence” pins how each cell was verified; live-data cells were validated
2026-09-29 against LIVE ``Data.p4k`` (150 GB) and ``Data/Game2.dcb``.

Pack formats
------------

+--------------------------------+------------+----------------------------------------------------------+
| Format                         | Status     | Evidence                                                 |
+================================+============+==========================================================+
| P4K v1 (ZIP central directory) | ✅ native  | LIVE opens: 1,366,371 files in ~11 s; skipped-tags matrix |
|                                |            | recorded (0x0000/0x0001/0x0002 + ~2000 CIG 0xf6xx–0xffxx  |
|                                |            | tags); ``tests/test_p4k_tolerant_cdr.py`` (8 tests)      |
+--------------------------------+------------+----------------------------------------------------------+
| P4K v2 ("JiJi", 0xAF trailer)  | ✅ native  | Round-trip vs svarog-generated v2 pack byte-identical;   |
|                                |            | ``tests/test_p4k_v2.py`` (5 tests). No live v2 pack      |
|                                |            | observed yet — extension CDR sections warn-and-continue. |
+--------------------------------+------------+----------------------------------------------------------+

Compression methods (R-SC-011 registry)
---------------------------------------

+--------+-----------------+---------------------------------------------------+
| Method | Decoder         | Evidence                                          |
+========+=================+===================================================+
| 0      | stored          | LIVE: 128,615 files read back size-exact          |
+--------+-----------------+---------------------------------------------------+
| 8      | raw deflate     | stdlib inline path (no LIVE samples observed)     |
+--------+-----------------+---------------------------------------------------+
| 93     | zstd (shared)   | synthetic round-trip; modern frames decode        |
+--------+-----------------+---------------------------------------------------+
| 100    | zstd (shared)   | LIVE: 1,237,756 files; 1 MB .dds read size-exact  |
+--------+-----------------+---------------------------------------------------+
| 101    | zlib deflate    | synthetic round-trip                              |
+--------+-----------------+---------------------------------------------------+
| other  | refuse w/ name  | ``ValueError`` naming the entry (tested: 42)      |
+--------+-----------------+---------------------------------------------------+

.. note::
   Method 93 covers modern zstd frames. Pre-1.0 legacy frames are rejected
   by the decoder per file (no silent garbage); no legacy-framed samples
   have been observed in the wild.

DCB versions
------------

+---------+-----------------+---------------------------------------------------+
| Version | Record layout   | Evidence                                          |
+=========+=================+===================================================+
| v5      | 32-byte classic | synthetic parse tests; byte-identical paths       |
+---------+-----------------+---------------------------------------------------+
| v6      | 32-byte classic | synthetic parse tests; byte-identical paths       |
+---------+-----------------+---------------------------------------------------+
| v8      | 36-byte fixed   | LIVE ``Game2.dcb`` (332 MB): 117022 records /     |
|         | (+team_offset,  | 6694 structs; full oracle extract (62062 files)   |
|         | struct_size)    | filename-identical both ways; ANVL_Arrow          |
|         |                 | name/GUID/properties field-match vs svarog 19h    |
|         |                 | v2.0.3 macOS prebuilt                             |
+---------+-----------------+---------------------------------------------------+
| other   | refuse w/ name  | ``DataCoreVersionError`` naming the version       |
+---------+-----------------+---------------------------------------------------+

Oracle
------

`svarog <https://github.com/19h/svarog>`_ v2.0.3 (macOS-aarch64 prebuilt,
SHA256-verified) is the record-layout oracle: ``dcb-extract`` for dump
diffs, ``p4k-create``/``p4k-convert-v2`` for v2 fixture generation.
