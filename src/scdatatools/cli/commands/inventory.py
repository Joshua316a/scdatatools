import json
import sys
from pathlib import Path


def inventory(scdir: Path, outfile: Path):
    # Late import: parser construction (including --help) must not require
    # the game-data stack.
    from scdatatools.sc import StarCitizen

    sc = StarCitizen(scdir)
    i = sc.generate_inventory()

    try:
        with open(outfile, "w") as o:
            # default=str will handle the datetime objects
            print(f"Writing {outfile.name}")
            json.dump(i, o, indent=2, default=str)
    except KeyboardInterrupt:
        sys.stderr.write("\nExiting, the inventory file may not be complete...\n\n")


def register_inventory(subparsers, parents):
    """Register `scdt inventory` (argparse translation of the nubia decorators)."""
    cmd = subparsers.add_parser(
        "inventory",
        parents=parents,
        help="Dumps a JSON object of every file in the Star Citizen directory and archives (recursively). This can be "
        "used to compare different versions of Star Citizen",
        description="Dumps a JSON object of every file in the Star Citizen directory and archives (recursively).",
    )
    cmd.add_argument(
        "scdir",
        metavar="scdir<STR>",
        type=Path,
        help="StarCitizen Game Folder",
    )
    cmd.add_argument(
        "outfile",
        metavar="outfile<STR>",
        type=Path,
        help="Output file name",
    )
    cmd.set_defaults(_handler=lambda ns: inventory(
        scdir=ns.scdir,
        outfile=ns.outfile,
    ))
    return cmd
