import argparse
import logging
import sys
import typing
from pathlib import Path


logger = logging.getLogger(__name__)


class _CliContext:
    """Process-wide CLI context (replaces nubia's Context object).

    Populated once from the parsed global options by ``scdatatools.cli.main``
    before dispatch; command bodies read it via :func:`get_context`.
    """

    cache_dir = None
    verbose = 0


_CTX = _CliContext()


def get_context() -> _CliContext:
    return _CTX


def open_sc_dir(sc_dir: typing.Union[str, Path]):
    """Processes the `sc_dir` CLI argument and returns a `StarCitizen` object. This function will error and exit the
    program if it fails to open the given `sc_dir`.
    """
    # Late imports: parser construction (including --help) must not require
    # the game-data stack.
    from scdatatools.launcher import get_installed_sc_versions
    from scdatatools.sc import StarCitizen

    installed_versions = get_installed_sc_versions()
    if str(sc_dir).upper() in installed_versions and not Path(sc_dir).is_dir():
        sc_dir = installed_versions[sc_dir.upper()]
        logger.debug(f"Using installed version {sc_dir}")

    ctx = get_context()
    sc_dir = Path(sc_dir).expanduser()
    if sc_dir.is_file():
        if sc_dir.suffix == ".p4k":
            sc_dir = sc_dir.parent
        else:
            sys.stderr.write(
                "Invalid argument for sc_dir. Must be a Star Citizen installation directory or a Data.p4k file\n"
            )
            sys.exit(1)

    try:
        sc = StarCitizen(sc_dir, cache_dir=ctx.cache_dir)
    except Exception as e:
        sys.stderr.write(f"Unable to open StarCitizen data: {e}\n")
        sys.exit(1)
    return sc


def dash(name: str) -> str:
    """CLI spelling for a Python argument name (nubia compatibility)."""
    return "--" + name.replace("_", "-")


EXTRACTION_ARGS = {
    "convert_cryxml": {
        "type": str,
        "description": "Automatically convert CryXmlB files to specified format.",
        "choices": ["xml", "json"],
        "aliases": ["-c"],
    },
    "extract_model_assets": {
        "type": bool,
        "description": "Automatically select and extract assets (materials and textures) for model files "
        "that are being extracted, in addition to the search filter",
        "aliases": ["-A"],
    },
    "unsplit_textures": {
        "type": bool,
        "description": "Automatically recombine split .dds texture files",
        "aliases": ["-T"],
    },
    "convert_textures": {
        "type": str,
        "aliases": ["-t"],
        "description": "Convert textures to the given image format. This also enables unsplit_textures.",
        "choices": ["png", "tif", "tga"],
    },
    "convert_models": {
        "type": bool,
        "description": "Automatically convert 3d models to COLLADA.",
        "aliases": ["-m"],
    },
    "no_overwrite": {
        "type": bool,
        "description": "Do not overwrite existing files.",
        "aliases": ["-O"],
    },
    "output": {
        "type": str,
        "description": "The output directory to extract files into or the output path if --single. "
        "Defaults to current directory",
        "aliases": ["-o"],
    },
}


def add_option(parser, name, type_, default, description, aliases=(), choices=None):
    """Add one option mirroring nubia's rendering (dashes, type metavars)."""
    # nubia compatibility: aliases with dashes are used verbatim; bare words
    # become --long options (e.g. aliases=["png"] -> --png STR).
    flags = [dash(name)] + [a if a.startswith("-") else "--" + a for a in aliases]
    kwargs = {"help": description, "default": default}
    if type_ is bool:
        kwargs["action"] = "store_true"
    elif type_ == "list":
        kwargs["nargs"] = "*"
        kwargs["metavar"] = "str"
    elif choices is None:
        # Plain strings render with nubia's STR metavar; choices render as
        # {a,b} (metavar would suppress that).
        kwargs["metavar"] = "STR"
    if choices:
        kwargs["choices"] = choices
    parser.add_argument(*flags, **kwargs)


def add_sc_dir_argument(parser):
    """Adds the `sc_dir` positional (Star Citizen dir or Data.p4k file)."""
    parser.add_argument(
        "sc_dir",
        metavar="sc_dir<STR>",
        help="Star Citizen installation directory or Data.p4k file. You can also specify LIVE or PTU and scdt "
        "will attempt to find the installed versions of Star Citizen.",
    )


def add_extraction_args(parser, exclude=None, defaults=None):
    """Adds the shared p4k extraction options (all optional flags).

    `defaults` maps option names to the command signature's defaults, so
    `--help` and dispatch match the previous interface exactly.
    """
    excluded = set(exclude or [])
    given = defaults or {}
    for arg_name, params in EXTRACTION_ARGS.items():
        if arg_name in excluded:
            continue
        if arg_name not in given:
            raise KeyError(
                f"add_extraction_args: no default given for {arg_name!r} "
                "(pass the command signature's defaults)"
            )
        add_option(
            parser,
            arg_name,
            params["type"],
            given.get(arg_name),
            params["description"],
            aliases=params.get("aliases", []),
            choices=params.get("choices"),
        )


def add_global_options(parser):
    """Adds --verbose/-v and --cache-dir/-C (present on every command)."""
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity, can be specified multiple times",
    )
    parser.add_argument(
        "--cache-dir",
        "-C",
        default=None,
        metavar="CACHE_DIR",
        help="Set a cache directory for scdt to use for faster loading times for some commands. The cache directory"
        " can also be set with the SCDT_CACHE_DIR environment variable.",
    )
