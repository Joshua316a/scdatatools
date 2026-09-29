import io
import json

from . import common


def actionmap(
    sc_dir: str,
    csv: bool = False,
):
    sc = common.open_sc_dir(sc_dir)
    am = sc.default_profile.actionmap()

    if csv:
        out = io.StringIO(newline="")
        sc.default_profile.dump_actionmap_csv(out)
        print(out.getvalue())
    else:
        print(json.dumps(am, indent=4))


def register_actionmap(subparsers, parents):
    """Register `scdt actionmap` (argparse translation of the nubia decorators)."""
    cmd = subparsers.add_parser(
        "actionmap",
        parents=parents,
        help="Dumps the default profile action map (keybinds) as JSON",
        description="Dumps the default profile action map (keybinds) as JSON",
    )
    common.add_sc_dir_argument(cmd)
    common.add_option(
        cmd, "csv", bool, False,
        "Output as a CSV instead",
        aliases=["-c"],
    )
    cmd.set_defaults(_handler=lambda ns: actionmap(
        sc_dir=ns.sc_dir,
        csv=ns.csv,
    ))
    return cmd
