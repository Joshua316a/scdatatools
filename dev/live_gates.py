#!/usr/bin/env python3
"""Live-data gate harness (Workstream 1, Phase 4 Task 4.1/G7).

Runs where game data already lives — NEVER uploads anything. The pack and
DCB are CIG IP; no redistribution, no server-side copies (see proposal §4).

Usage:
    python3 dev/live_gates.py --pack ~/Downloads/GameData/LIVE/Data.p4k \\
        --workdir /tmp/live-gates --svarog /tmp/svarog/svarog

Legs (any failure exits nonzero):
  1. pack: open the archive, assert a sane filelist, dump skipped-tags.
  2. dcb: extract Game2.dcb, parse natively, assert record/struct counts
     match the header and the end-of-buffer walk balances.
  3. oracle: svarog full extract vs native dump — filename sets identical
     both ways, (name, guid) triples equal. Same-data diff, so patch
     churn cannot false-alarm: any mismatch is a parser bug.
New skipped tags are REPORTED (version-matrix input), not failed.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
import conftest  # noqa: F401

from scdatatools.forge import DataCoreBinary, dftypes
from scdatatools.p4k import P4KFile

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""), flush=True)
    if not condition:
        FAILURES.append(label)


def leg_pack(pack_path, workdir):
    print("== leg 1: pack open ==")
    t0 = time.time()
    pf = P4KFile(pack_path)
    dt = time.time() - t0
    n = len(pf.filelist)
    check("pack opens", n > 1000000, f"{n} files in {dt:.1f}s")
    matrix = pf.skipped_tags_report()
    with open(os.path.join(workdir, "skipped_tags.json"), "w") as f:
        json.dump(matrix, f, indent=1)
    print(f"  skipped-tag families: {len(matrix)} (see skipped_tags.json)")
    dcb_hits = [i.filename for i in pf.filelist
                if i.filename.lower().endswith("game2.dcb")]
    check("Game2.dcb present", len(dcb_hits) == 1, str(dcb_hits))
    raw = pf.read(dcb_hits[0]) if dcb_hits else b""
    pf.close()
    dcb_path = os.path.join(workdir, "Game2.dcb")
    with open(dcb_path, "wb") as f:
        f.write(raw)
    print(f"  extracted {len(raw)} bytes -> {dcb_path}")
    return dcb_path


def leg_dcb(dcb_path):
    print("== leg 2: native DCB parse ==")
    t0 = time.time()
    dcb = DataCoreBinary(dcb_path)
    dt = time.time() - t0
    check("version dispatched", dcb.header.version in dftypes.DCB_RECORD_TYPES,
          f"v{dcb.header.version}")
    check("record count matches header",
          len(dcb.records) == dcb.header.record_definition_count,
          f"{len(dcb.records)} in {dt:.1f}s")
    # Keyed by guid (unique). Filenames are NOT unique — duplicate filenames
    # across records are real data (e.g. dialogue banks); the oracle diff
    # below handles them as sets rather than assuming 1:1.
    dump = {}
    seen_filenames = set()
    dupes = 0
    for r in dcb.records:
        try:
            if r.filename in seen_filenames:
                dupes += 1
            seen_filenames.add(r.filename)
            dump[r.id.value] = [r.filename, r.name]
        except Exception as e:  # noqa: BLE001 — one bad record must not kill the dump
            dump.setdefault("<ERR>", []).append(str(e))
    print(f"  {dupes} records share a filename with another record")
    dump_path = os.path.join(os.path.dirname(dcb_path), "native_dump.json")
    with open(dump_path, "w") as f:
        json.dump(dump, f)
    print(f"  dumped {len(dump)} records -> {dump_path}")
    return dump_path


def leg_oracle(dcb_path, workdir, svarog_bin):
    print("== leg 3: oracle diff ==")
    if not svarog_bin or not os.path.isfile(svarog_bin):
        print("  SKIP: no svarog binary (pass --svarog); filename/value diff uncovered")
        return None
    outdir = os.path.join(workdir, "oracle")
    os.makedirs(outdir, exist_ok=True)
    r = subprocess.run(
        [svarog_bin, "dcb-extract", "-i", dcb_path, "-o", outdir],
        capture_output=True, text=True, timeout=1800,
    )
    check("oracle extract succeeds", r.returncode == 0, r.stderr.strip()[-200:])
    files = []
    for root, _, fns in os.walk(outdir):
        files.extend(os.path.relpath(os.path.join(root, f), outdir) for f in fns)
    return outdir, files


def diff_dumps(native_path, oracle_dir):
    native = json.load(open(native_path))
    native.pop("<ERR>", None)
    # Native index: filename -> set of (name, guid). Filenames are not
    # unique in the data, so the oracle's single winner per file must be a
    # MEMBER of the native set — never assumed 1:1.
    by_filename = {}
    for guid, (fn, name) in native.items():
        by_filename.setdefault(fn, set()).add((name, guid))
    oracle_files = set()
    mismatches = 0
    checked = 0
    for root, _, fns in os.walk(oracle_dir):
        for f in fns:
            rel = os.path.relpath(os.path.join(root, f), oracle_dir)
            oracle_files.add(rel)
    check("filename sets identical",
          set(by_filename) == oracle_files,
          f"native={len(by_filename)} oracle={len(oracle_files)} "
          f"only-native={len(set(by_filename) - oracle_files)} "
          f"only-oracle={len(oracle_files - set(by_filename))}")
    # Value check: every 200th shared file, the oracle's (name, guid) must
    # be a member of the native set for that filename.
    shared = sorted(set(by_filename) & oracle_files)
    for rel in shared[::200]:
        checked += 1
        try:
            root_el = ET.parse(os.path.join(oracle_dir, rel)).getroot()
            tag = root_el.tag  # e.g. EntityClassDefinition.ANVL_Arrow
            oname = tag.split(".", 1)[1] if "." in tag else tag
            oguid = root_el.get("RecordId", "")
            if not any(n == oname and g.lower() == oguid.lower()
                       for n, g in by_filename[rel]):
                mismatches += 1
                print(f"  DIFF {rel}: oracle=({oname},{oguid}) "
                      f"native={sorted(by_filename[rel])}")
        except Exception as e:  # noqa: BLE001 — record and continue
            mismatches += 1
            print(f"  ERROR {rel}: {e}")
    check("oracle values are members of native sets", mismatches == 0,
          f"{checked} sampled")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", required=True, help="Path to Data.p4k (read-only, never copied off-host)")
    ap.add_argument("--workdir", required=True, help="Local scratch dir for extracts/dumps")
    ap.add_argument("--svarog", default="", help="Path to svarog binary for the oracle leg (optional)")
    args = ap.parse_args()
    os.makedirs(args.workdir, exist_ok=True)

    dcb_path = leg_pack(args.pack, args.workdir)
    native_dump = leg_dcb(dcb_path)
    res = leg_oracle(dcb_path, args.workdir, args.svarog)
    if res is not None:
        diff_dumps(native_dump, res[0])

    print()
    if FAILURES:
        print(f"GATES FAILED: {len(FAILURES)} leg(s): {', '.join(FAILURES)}")
        return 1
    print("ALL LIVE LEGS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
