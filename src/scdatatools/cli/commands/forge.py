import logging
import sys
import typing
from itertools import chain
from pathlib import Path

from rich import get_console, table

from scdatatools.forge import DataCoreBinary
from . import common
from ..utils import track

if typing.TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


def _dump_record(dcb, record, output, guid, guid_if_exists, xml):
    if output == "-":
        if xml:
            sys.stdout.write(dcb.dump_record_xml(record) + "\n")
        else:
            sys.stdout.write(dcb.dump_record_json(record) + "\n")
    else:
        if output.is_dir():
            output = output / Path(record.filename)
        output.parent.mkdir(parents=True, exist_ok=True)
        suffix = ".xml" if xml else ".json"
        if guid or (guid_if_exists and output.is_file()):
            output = output.parent / f"{output.stem}.{record.id.value}{suffix}"
        else:
            output = output.parent / f"{output.stem}{suffix}"
        logger.info(str(output))
        try:
            with open(output, "w") as target:
                if xml:
                    target.write(dcb.dump_record_xml(record))
                else:
                    target.write(dcb.dump_record_json(record))
        except ValueError as e:
            print(f"ERROR: Error processing {record.filename}: {e}")


def add_forge_common_args(parser):
    """Adds the shared forge-file positional and filter option."""
    parser.add_argument(
        "forge_file",
        metavar="forge_file<STR>",
        help="DataForge (.dcb) file to extract data from. (or Data.p4k or Star Citizen installation directory)",
    )
    common.add_option(
        parser, "filter", "list", ["*"],
        "Posix style file filter of which files to extract",
        aliases=["-f"],
    )


def parse_forge_args(forge_file, filter):
    forge_file = Path(forge_file).expanduser()
    filters = [_.strip("'").strip('"') for _ in filter]

    if forge_file.suffix.casefold() == ".p4k" or forge_file.is_dir():
        logger.info(f"Opening DataCore from {forge_file}")
        dcb = common.open_sc_dir(forge_file).datacore
    else:
        logger.info(f"Opening DataForge file: {forge_file}")
        dcb = DataCoreBinary(str(forge_file))

    # using the dict like this ends up removing duplicated but keeping the order of insertion
    records = dict(chain((str(r.id), r) for f in filters for r in dcb.search_filename(f)))
    return dcb, filters, records


class forge:
    """Tools for interacting with the Dataforge database"""

    def ls(self, forge_file: str, filter: typing.List[str] = ("*",)):
        """List records in the Data Core"""
        dcb, filters, records = parse_forge_args(forge_file, filter)
        logger.info(f"{filters = }")

        # TODO: add more ls type formatting flags

        t = table.Table(box=None)
        t.add_column("GUID")
        t.add_column("filename")
        for r in records.values():
            t.add_row(str(r.id), r.filename)
        get_console().print(t)

    def extract(
        self,
        forge_file: typing.Text,
        filter: typing.List[str] = ("*",),
        output: typing.Text = ".",
        guid: bool = False,
        guid_if_exists: bool = True,
        xml: bool = True,
        json: bool = False,
        single: bool = False,
    ):
        """Extracts DataCore records and converts them to a given format (xml/json). Use the `--filter` argument
        to down-select which records to extract, by default it will extract all of them to the `--output` directory."""
        dcb, filters, records = parse_forge_args(forge_file, filter)
        output = Path(output).absolute() if output != "-" else output

        if single:
            print(f"Extracting first match for filters '{','.join(filters)}' to {output}")
            print("=" * 120)
            if not records:
                sys.stderr.write("No files found for filter")
                sys.exit(2)
            _dump_record(dcb, next(iter(records.values())), output, guid, guid_if_exists, not json)
        else:
            print(f"Extracting files into {output} with filter '{filters}'")
            print("=" * 120)
            try:
                if output == "-":
                    # don't output the progress bar if we're dumping to the console
                    for record in records.values():
                        _dump_record(dcb, record, output, guid, guid_if_exists, not json)
                else:
                    output = Path(output)
                    output.mkdir(parents=True, exist_ok=True)
                    for record in track(records.values(), description="Extracting records", unit="records"):
                        _dump_record(dcb, record, output, guid, guid_if_exists, not json)
            except KeyboardInterrupt:
                pass


def register_forge(subparsers, parents):
    """Register `scdt forge` (argparse translation of the nubia decorators)."""
    group = subparsers.add_parser(
        "forge",
        parents=parents,
        help="Tools for interacting with the Dataforge database",
        description="Tools for interacting with the Dataforge database",
    )
    subs = group.add_subparsers(dest="forge_command", metavar="[subcommand]")
    inst = forge()

    ls = subs.add_parser(
        "ls",
        parents=parents,
        help="List records in the Data Core",
        description="List records in the Data Core",
    )
    add_forge_common_args(ls)
    ls.set_defaults(_handler=lambda ns: inst.ls(
        forge_file=ns.forge_file,
        filter=ns.filter,
    ))

    ex = subs.add_parser(
        "extract",
        aliases=["x"],
        parents=parents,
        help="Extracts DataCore records and converts them to a given format (xml/json). Use the `--filter` argument "
        "to down-select which records to extract, by default it will extract all of them to the `--output` directory.",
        description="Extracts DataCore records and converts them to a given format (xml/json).",
    )
    add_forge_common_args(ex)
    common.add_option(
        ex, "single", bool, False,
        "Extract first matching file only", aliases=["-1"],
    )
    common.add_option(
        ex, "guid", bool, False,
        "Include the GUID in the filename (avoids overwriting from records with the same 'filename') "
        "(Default: False)",
        aliases=["-g"],
    )
    common.add_option(
        ex, "guid_if_exists", bool, True,
        "Include the GUID in the filename only if the output file already exists. (Default: True)",
        aliases=["-G"],
    )
    fmt = ex.add_mutually_exclusive_group()
    fmt.add_argument("--xml", "-x", action="store_true", default=True, help="Convert to XML (Default)")
    fmt.add_argument("--json", "-j", action="store_true", default=False, help="Convert to JSON")
    common.add_option(
        ex, "output", str, ".",
        "The output directory to extract files into or the output path if --single. "
        "Defaults to current directory. Use '-' to output a single file to the stdout",
        aliases=["-o"],
    )
    ex.set_defaults(_handler=lambda ns: inst.extract(
        forge_file=ns.forge_file,
        filter=ns.filter,
        output=ns.output,
        guid=ns.guid,
        guid_if_exists=ns.guid_if_exists,
        xml=ns.xml,
        json=ns.json,
        single=ns.single,
    ))
    return group
