import json
import sys
import typing
from pathlib import Path

from scdatatools.engine.cryxml import (
    etree_from_cryxml_file,
    dict_from_cryxml_file,
    is_cryxmlb_file,
)
from scdatatools.engine.cryxml.utils import pprint_xml_tree

from . import common


def _do_conversions(cryxml_file, replace, output, fmt):
    if replace:
        output = Path(cryxml_file)

    with Path(cryxml_file).open("rb") as cxml:
        if is_cryxmlb_file(cxml):
            if fmt == "xml":
                d = pprint_xml_tree(etree_from_cryxml_file(cxml))
            else:
                d = json.dumps(dict_from_cryxml_file(cxml), indent=2)
        else:
            sys.stderr.write(f"{cryxml_file} is not a CryXmlB file\n")
            return False

    if output == "-":
        print(d)
    else:
        with open(output, "w") as f:
            f.write(d)
    return True


def cryxml_to_xml(cryxml_file: typing.Text, replace: bool = False, output: typing.Text = "-"):
    _do_conversions(cryxml_file, replace, output, "xml")


def cryxml_to_json(cryxml_file: typing.Text, replace: bool = False, output: typing.Text = "-"):
    if _do_conversions(cryxml_file, replace, output, "json") and replace:
        Path(cryxml_file).unlink(missing_ok=True)


def _add_cryxml_args(parser, replace_help, output_help):
    parser.add_argument(
        "cryxml_file",
        metavar="cryxml-file<STR>",
        help="CryXML to convert",
    )
    common.add_option(
        parser, "replace", bool, False,
        replace_help,
        aliases=["-r"],
    )
    common.add_option(
        parser, "output", str, "-",
        output_help,
        aliases=["-o"],
    )


def register_cryxml_to_xml(subparsers, parents):
    cmd = subparsers.add_parser(
        "cryxml-to-xml",
        parents=parents,
        help="Convert a CryXML file to xml",
        description="Convert a CryXML file to xml",
    )
    _add_cryxml_args(
        cmd,
        "Convert the file in place",
        "Output filename or '-' for stdout. Defaults to '-'. Ignored if --replace is set.",
    )
    cmd.set_defaults(_handler=lambda ns: cryxml_to_xml(
        cryxml_file=ns.cryxml_file,
        replace=ns.replace,
        output=ns.output,
    ))
    return cmd


def register_cryxml_to_json(subparsers, parents):
    cmd = subparsers.add_parser(
        "cryxml-to-json",
        parents=parents,
        help="Convert a CryXML file to JSON",
        description="Convert a CryXML file to JSON",
    )
    _add_cryxml_args(
        cmd,
        "Convert the file in place. (will change the extension to .json)",
        "Output filename or '-' for stdout. Defaults to '-'",
    )
    cmd.set_defaults(_handler=lambda ns: cryxml_to_json(
        cryxml_file=ns.cryxml_file,
        replace=ns.replace,
        output=ns.output,
    ))
    return cmd
