"""
tests/test_cli_argparse.py — nubia → argparse translation fidelity.

No game data needed: builds the parser and asserts namespaces, defaults,
and help/usage parity with the pre-rewrite nubia interface (captured help
outputs are encoded below as EXPECTED_FLAGS per leaf command).
"""

import io
import os
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conftest  # noqa: F401  (package stub bootstrap)

from scdatatools.cli import build_parser, main


@pytest.fixture(scope="module")
def parser():
    return build_parser()


def _flags(help_text):
    """Extract --long-flag tokens from argparse help output."""
    import re

    return set(re.findall(r"--[\w-]+", help_text))


def _help(parser, argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            parser.parse_args(argv + ["--help"])
        except SystemExit as e:
            assert e.code == 0
    return buf.getvalue()


# Leaf command -> argv (sans executable) exercising positionals only.
LEAVES = {
    ("p4k", "extract"): ["p4k", "extract", "mydir"],
    ("forge", "ls"): ["forge", "ls", "game.dcb"],
    ("forge", "extract"): ["forge", "extract", "game.dcb"],
    ("blueprint", "generate"): ["blueprint", "generate", "mydir", "Ent"],
    ("blueprint", "extract"): ["blueprint", "extract", "mydir", "Ent", "out"],
    ("localization", "translate"): ["localization", "translate", "mydir", "hello"],
    ("localization", "ls"): ["localization", "ls", "mydir"],
    ("localization", "export"): ["localization", "export", "mydir", "out.csv"],
    ("tex", "convert"): ["tex", "convert", "a.dds"],
    ("tex", "dds-unsplit"): ["tex", "dds-unsplit", "a.dds"],
    ("blender", "install-addon"): ["blender", "install-addon"],
    ("cryxml-to-xml",): ["cryxml-to-xml", "a.mtl"],
    ("cryxml-to-json",): ["cryxml-to-json", "a.mtl"],
    ("inventory",): ["inventory", "scdir", "out.json"],
    ("actionmap",): ["actionmap", "mydir"],
}

# Leaf -> long flags the nubia interface exposed (from captured --help).
EXPECTED_FLAGS = {
    ("p4k", "extract"): {"--single", "--output", "--file-filter", "--convert-cryxml",
                          "--extract-model-assets", "--unsplit-textures", "--convert-textures",
                          "--convert-models", "--no-overwrite"},
    ("forge", "ls"): {"--filter"},
    ("forge", "extract"): {"--filter", "--output", "--guid", "--guid-if-exists",
                            "--xml", "--json", "--single"},
    ("blueprint", "generate"): {"--output"},
    ("blueprint", "extract"): {"--convert-cryxml", "--unsplit-textures", "--convert-textures",
                                "--convert-models", "--no-overwrite"},
    ("localization", "translate"): {"--languages"},
    ("localization", "ls"): {"--filter", "--languages"},
    ("localization", "export"): {"--filter", "--languages"},
    ("tex", "convert"): {"--output-format", "--png", "--outdir", "--converter", "--quiet"},
    ("tex", "dds-unsplit"): {"--outdir", "--quiet", "--replace"},
    ("blender", "install-addon"): {"--version", "--include-path", "--list-versions"},
    ("cryxml-to-xml",): {"--replace", "--output"},
    ("cryxml-to-json",): {"--replace", "--output"},
    ("inventory",): set(),
    ("actionmap",): {"--csv"},
}


def test_all_leaves_parse_with_signature_defaults(parser):
    for key, argv in LEAVES.items():
        ns = parser.parse_args(argv)
        assert callable(getattr(ns, "_handler", None)), key


def _help_argv(key):
    # Command path without positionals (--help needs no operands).
    return list(key)


def test_leaf_flag_sets_match_nubia(parser):
    for key in LEAVES:
        text = _help(parser, _help_argv(key))
        got = _flags(text) - {"--help", "--verbose", "--cache-dir"}
        want = EXPECTED_FLAGS[key]
        assert want <= got, f"{key}: missing flags {want - got}"
        assert not (got - want), f"{key}: extra flags {got - want}"


def test_signature_defaults_preserved(parser):
    ns = parser.parse_args(["p4k", "extract", "mydir"])
    assert (ns.output, ns.file_filter, ns.single, ns.no_overwrite) == (".", "*", False, False)
    assert ns.convert_cryxml == "" and ns.convert_textures == ""
    assert ns.extract_model_assets is False and ns.convert_models is False

    ns = parser.parse_args(["forge", "extract", "game.dcb"])
    assert ns.filter == ["*"] and ns.output == "."
    assert ns.guid is False and ns.guid_if_exists is True
    assert ns.xml is True and ns.json is False and ns.single is False

    ns = parser.parse_args(["blueprint", "extract", "d", "e", "o"])
    assert ns.convert_cryxml == "xml" and ns.unsplit_textures is True

    ns = parser.parse_args(["localization", "translate", "d", "hi"])
    assert ns.languages is None

    ns = parser.parse_args(["tex", "convert", "a.dds"])
    assert (ns.output_format, ns.outdir, ns.converter, ns.quiet) == ("png", "", "texconv", False)

    ns = parser.parse_args(["blender", "install-addon"])
    assert ns.version is None and ns.list_versions is False and ns.include_path == []

    ns = parser.parse_args(["cryxml-to-json", "a.mtl"])
    assert (ns.replace, ns.output) == (False, "-")


def test_list_options_accept_multiples(parser):
    ns = parser.parse_args(["forge", "ls", "g.dcb", "--filter", "a*", "b*"])
    assert ns.filter == ["a*", "b*"]
    ns = parser.parse_args(["localization", "translate", "d", "hi", "-l", "english", "german"])
    assert ns.languages == ["english", "german"]


def test_exclusive_xml_json_group(parser):
    ns = parser.parse_args(["forge", "extract", "g.dcb", "--json"])
    assert ns.json is True
    with pytest.raises(SystemExit):
        parser.parse_args(["forge", "extract", "g.dcb", "--xml", "--json"])


def test_aliases_preserved(parser):
    ns = parser.parse_args(["p4k", "extract", "d", "-o", "out", "-f", "*.cgf", "-1"])
    assert (ns.output, ns.file_filter, ns.single) == ("out", "*.cgf", True)
    ns = parser.parse_args(["blueprint", "generate", "d", "E", "-o", "-"])
    assert ns.output == "-"


def test_group_aliases_preserved(parser):
    assert parser.parse_args(["bp", "generate", "d", "E"]).command == "bp"
    assert parser.parse_args(["loc", "ls", "d"]).command == "loc"
    assert parser.parse_args(["forge", "x", "g.dcb"]).forge_command == "x"
    assert parser.parse_args(["p4k", "x", "d"]).p4k_command == "x"


def test_choices_render_in_usage(parser):
    text = _help(parser, ["p4k", "extract"])
    assert "--convert-cryxml {xml,json}" in text
    assert "--convert-textures {png,tif,tga}" in text
    text = _help(parser, ["forge", "extract"])
    assert "[--xml | --json]" in text


def test_no_command_prints_help_and_returns_2(capsys):
    assert main([]) == 2
    out = capsys.readouterr().out
    assert "blender" in out and "forge" in out and "p4k" in out


def test_top_level_commands_match_nubia(parser):
    actions = None
    for action in parser._actions:
        from argparse import _SubParsersAction

        if isinstance(action, _SubParsersAction):
            actions = set(action.choices)
    # Ground truth from nubia --help, minus the external `connect` plugin.
    assert {"blender", "blueprint", "bp", "cryxml-to-json", "cryxml-to-xml",
            "forge", "inventory", "localization", "loc", "p4k", "actionmap",
            "tex"} <= actions
