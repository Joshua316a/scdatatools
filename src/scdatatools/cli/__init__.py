import sys


def main():
    # nubia (the `scdt` CLI framework) is an optional `cli` extra, importable
    # only on Python < 3.12 — it must never load at package import time.
    # Library use (`scdatatools.p4k`, `scdatatools.forge`, …) stays nubia-free
    # (R-SC-015).
    try:
        from nubia import Nubia, Options
    except ImportError as e:
        print(
            "The `scdt` CLI needs the optional `cli` extra "
            "(pip install 'scdatatools[cli]', Python < 3.12 required): "
            f"{e}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    from scdatatools.cli import commands
    from scdatatools.plugins import plugin_manager

    from .plugin import SCDTNubiaPlugin

    plugin_manager.setup()
    shell = Nubia(
        name="scdt",
        plugin=SCDTNubiaPlugin(),
        command_pkgs=commands,
        options=Options(persistent_history=False),
    )

    sys.exit(shell.run())
