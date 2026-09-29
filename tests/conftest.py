"""Test bootstrap for the scdatatools fork (Workstream 1).

Library modules (p4k, forge, …) are tested in isolation from the heavy
`scdatatools/__init__.py` chain (`sc` → CLI → nubia/rsi/sentry/…), which
needs the full install footprint. A stub parent package with the real
`__path__` lets `scdatatools.p4k` etc. resolve while skipping the package
init. Only real runtime deps (zstandard, pycryptodome, xxhash, numpy,
pyquaternion) are required — see /tmp/scfork-test-venv.
"""

import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC_PKG = os.path.join(_ROOT, "src", "scdatatools")


def _install_package_stub():
    if "scdatatools" in sys.modules:
        return
    pkg = types.ModuleType("scdatatools")
    pkg.__path__ = [_SRC_PKG]
    sys.modules["scdatatools"] = pkg


_install_package_stub()
