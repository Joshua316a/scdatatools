import logging
import sys

from scdatatools import __version__
from scdatatools.cli import plugin
from scdatatools.cli.commands import (
    blender,
    blueprint,
    cryxml,
    forge,
    inventory,
    localization,
    p4k,
    profile,
    texture,
)
from scdatatools.cli.commands import common


def build_parser():
    """Build the full `scdt` argument tree.

    Faithful argparse translation of the previous nubia interface: identical
    command names, aliases, flags, defaults, and help text. The only
    behavioral delta is the top level — nubia dropped into an interactive
    shell when no command was given; argparse prints help and exits 2.
    """
    parser = plugin.get_opts_parser(add_help=True)
    parser.prog = "scdt"
    parser.description = f"scdt - Star Citizen Data Tools v{__version__}"

    globals_parent = plugin.get_opts_parser(add_help=False)
    parents = [globals_parent]

    subs = parser.add_subparsers(dest="command", metavar="[command]")
    blender.register_blender(subs, parents)
    blueprint.register_blueprint(subs, parents)
    cryxml.register_cryxml_to_xml(subs, parents)
    cryxml.register_cryxml_to_json(subs, parents)
    forge.register_forge(subs, parents)
    inventory.register_inventory(subs, parents)
    localization.register_localization(subs, parents)
    p4k.register_p4k(subs, parents)
    profile.register_actionmap(subs, parents)
    texture.register_tex(subs, parents)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 2

    # Apply global options (mirrors the old shell's validate_args).
    common.get_context().verbose = args.verbose or 0
    common.get_context().cache_dir = plugin.resolve_cache_dir(args)
    plugin.setup_logging(logging.root, args)

    handler(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
