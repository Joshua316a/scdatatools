import typing
from pathlib import Path

from scdatatools.blender.addon import install
from scdatatools.blender.utils import available_blender_installations

from . import common


class Blender:
    """Blender Integration"""

    def install_addon(
        self,
        version: typing.List[str] = None,
        list_versions: bool = False,
        include_path: typing.List[str] = tuple(),
    ):
        """Install the current scdatatools add-on into Blender."""
        include_path = [Path(_) for _ in include_path]

        if list_versions:
            print(
                "\n".join(
                    f' {v["version"]}:\t{v["path"]}'
                    for k, v in available_blender_installations(include_paths=include_path).items()
                    if v["compatible"]
                )
            )
            return

        if version is None:
            version = set(_["version"] for _ in available_blender_installations(include_paths=include_path).values())

        for v in version:
            print(f"Installed add-on to {str(install(v))}")


def register_blender(subparsers, parents):
    """Register `scdt blender` (argparse translation of the nubia decorators)."""
    group = subparsers.add_parser(
        "blender",
        parents=parents,
        help="Blender Integration",
        description="Blender Integration",
    )
    subs = group.add_subparsers(dest="blender_command", metavar="[subcommand]")
    inst = Blender()

    cmd = subs.add_parser(
        "install-addon",
        parents=parents,
        help="Install the current scdatatools add-on into Blender.",
        description="Install the current scdatatools add-on into Blender.",
    )
    common.add_option(
        cmd, "version", "list", None,
        "Blender version to install the add-on to. Absolute path, or Blender version number if "
        "installed to the default location",
        aliases=["-i"],
    )
    common.add_option(
        cmd, "include_path", "list", [],
        "Add additional locations to look for blender.exe",
        aliases=["-p"],
    )
    common.add_option(
        cmd, "list_versions", bool, False,
        "List detected Blender installations.",
        aliases=["-l"],
    )
    cmd.set_defaults(_handler=lambda ns: inst.install_addon(
        version=ns.version,
        list_versions=ns.list_versions,
        include_path=ns.include_path,
    ))
    return group
