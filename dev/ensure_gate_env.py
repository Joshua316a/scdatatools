#!/usr/bin/env python3
"""Create (once) and verify the live-gate venv (Workstream 1, G7).

The gate runner uses whatever `python3` is on PATH, which may lack the
harness dependencies. This script builds `.venv-gates` next to the repo
(first run only) with exactly the wheels the harness needs, then execs
`dev/live_gates.py` inside it. Idempotent: re-runs are a fast no-op when
the venv already satisfies the pins.

Usage (also used verbatim as the GATES.md G7 CHECK):
    python3 dev/ensure_gate_env.py --pack <Data.p4k> --workdir <dir> [--svarog <bin>]
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, ".venv-gates")
PINS = [
    "zstandard",
    "pycryptodome",
    "xxhash",
    "numpy",
    "pyquaternion",
]


def _venv_python():
    if os.name == "nt":
        return os.path.join(VENV, "Scripts", "python.exe")
    return os.path.join(VENV, "bin", "python")


def main(argv):
    if not os.path.isfile(_venv_python()):
        print(f"creating gate venv at {VENV} ...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
        subprocess.run(
            [_venv_python(), "-m", "pip", "install", "-q"] + PINS,
            check=True,
        )
    os.execv(_venv_python(), [_venv_python(), os.path.join(ROOT, "dev", "live_gates.py")] + argv)


if __name__ == "__main__":
    main(sys.argv[1:])
