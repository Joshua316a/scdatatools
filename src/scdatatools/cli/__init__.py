import sys

from nubia import Nubia, Options

from scdatatools.cli import commands
from scdatatools.plugins import plugin_manager

from .plugin import SCDTNubiaPlugin


def main():
    plugin_manager.setup()
    shell = Nubia(
        name="scdt",
        plugin=SCDTNubiaPlugin(),
        command_pkgs=commands,
        options=Options(persistent_history=False),
    )

    sys.exit(shell.run())
