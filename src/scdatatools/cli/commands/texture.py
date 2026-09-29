import os
import shutil
import sys
import typing
from pathlib import Path

from scdatatools.engine.textures import (
    collect_and_unsplit,
    tex_convert,
)
from scdatatools.engine.textures.converter import ConverterUtility
from scdatatools.engine.textures.dds import is_glossmap
from scdatatools.utils import NamedBytesIO

from . import common


class Tex:
    """Texture processing commands"""

    def dds_unsplit(
        self,
        dds_files: typing.List[str],
        outdir: str = "",
        quiet=False,
        replace: bool = False,
    ):
        files_to_process = set()
        for ddsfile in dds_files:
            ddsfile = Path(ddsfile).absolute()
            if ddsfile.is_dir():
                for dds in ddsfile.rglob("*.dds.[0-9]*"):
                    if is_glossmap(dds):
                        files_to_process.add(dds.parent / f'{dds.name.split(".")[0]}.dds.a')
                    else:
                        files_to_process.add(dds.parent / f'{dds.name.split(".")[0]}.dds')
            else:
                _ = Path(ddsfile)
                if is_glossmap(ddsfile):
                    files_to_process.add(_.parent / f'{_.name.split(".")[0]}.dds.a')
                else:
                    files_to_process.add(_.parent / f'{_.name.split(".")[0]}.dds')

        if outdir:
            outdir = Path(outdir).absolute()

        for ddsfile in files_to_process:
            try:
                if outdir:
                    outfile = outdir / f"{Path(ddsfile).name}"
                elif replace:
                    outfile = ddsfile
                else:
                    stem, ext = str(ddsfile.name).split(".", maxsplit=1)
                    outfile = (ddsfile.parent / f"{stem}_full.{ext}").absolute()

                outfile = collect_and_unsplit(ddsfile, outfile=outfile, remove=replace)
                if not quiet:
                    print(f"{ddsfile} -> {outfile}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                sys.stderr.write(f"Failed to convert {ddsfile}: {repr(e)}\n")
                sys.stderr.flush()

    def convert(
        self,
        dds_files: typing.List[str],
        output_format: str = "png",
        outdir: str = "",
        converter: str = "texconv",
        quiet=False,
    ):
        converter_bin = converter
        if not os.path.isfile(converter_bin):
            converter_bin = shutil.which(converter_bin)
        if not os.path.isfile(converter_bin):
            sys.stderr.write(
                "Could not determine which image converter to use. texconv or compressonatorcli is " "required"
            )
            sys.exit(1)

        if "texconv" in str(converter_bin).lower():
            converter = ConverterUtility.texconv
        else:
            converter = ConverterUtility.compressonator

        output_format = "." + output_format.lstrip(".").lower()
        files_to_process = set()
        for ddsfile in dds_files:
            ddsfile = Path(ddsfile).absolute()
            if ddsfile.is_dir():
                for dds in ddsfile.rglob("*.dds.[0-9]*"):
                    if is_glossmap(dds):
                        files_to_process.add(dds.parent / f'{dds.name.split(".")[0]}.dds.a')
                    else:
                        files_to_process.add(dds.parent / f'{dds.name.split(".")[0]}.dds')
            else:
                _ = Path(ddsfile)
                if is_glossmap(ddsfile):
                    files_to_process.add(_.parent / f'{_.name.split(".")[0]}.dds.a')
                else:
                    files_to_process.add(_.parent / f'{_.name.split(".")[0]}.dds')

        if outdir:
            outdir = Path(outdir).absolute()

        for ddsfile in files_to_process:
            try:
                if outdir:
                    outfile = outdir / f"{Path(ddsfile).stem}{output_format}"
                else:
                    outfile = Path(ddsfile).with_suffix(output_format).absolute()

                tex_convert(
                    NamedBytesIO(collect_and_unsplit(ddsfile), str(ddsfile)),
                    outfile,
                    converter=converter,
                    converter_bin=converter_bin,
                )
                if not quiet:
                    print(f"{ddsfile} -> {outfile}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                sys.stderr.write(f"Failed to convert {ddsfile}: {repr(e)}\n")
                sys.stderr.flush()


def _add_dds_files_positional(parser, description):
    parser.add_argument(
        "dds_files",
        nargs="*",
        metavar="dds-files<str>",
        help=description,
    )


def register_tex(subparsers, parents):
    """Register `scdt tex` (argparse translation of the nubia decorators)."""
    group = subparsers.add_parser(
        "tex",
        parents=parents,
        help="Texture processing commands",
        description="Texture processing commands",
    )
    subs = group.add_subparsers(dest="tex_command", metavar="[subcommand]")
    inst = Tex()

    unsplit = subs.add_parser(
        "dds-unsplit",
        parents=parents,
        help="Recombine split DDS texture files (dds.N). This will attempt to locate the DDS pieces.",
        description="Recombine split DDS texture files (dds.N). This will attempt to locate the DDS pieces.",
    )
    _add_dds_files_positional(
        unsplit,
        "DDS file to recombine. Split pieces will be found automatically. Directories "
        "will be searched recursively for split textures.",
    )
    common.add_option(
        unsplit, "outdir", str, "",
        "Output directory to place unsplit textures. By default, the output texture will be placed next "
        "to the input texture with '_full' appended to it's filename, or be replaced if -r is specified",
        aliases=["-o"],
    )
    common.add_option(unsplit, "quiet", bool, False, "Only print errors", aliases=["-q"])
    common.add_option(
        unsplit, "replace", bool, False,
        "Replace the DDS file and also remove the pieces. Only if not output directory is specified",
        aliases=["-r"],
    )
    unsplit.set_defaults(_handler=lambda ns: inst.dds_unsplit(
        dds_files=ns.dds_files,
        outdir=ns.outdir,
        quiet=ns.quiet,
        replace=ns.replace,
    ))

    convert = subs.add_parser(
        "convert",
        parents=parents,
        help="Convert DDS textures to another format.",
        description="Convert DDS textures to another format.",
    )
    _add_dds_files_positional(
        convert,
        "DDS file to converter. Split pieces will be found automatically. Directories "
        "will be searched recursively for split textures.",
    )
    # NOTE: aliases=["png"] renders as a --png STR alternate spelling,
    # exactly like the previous interface (verified against its --help).
    common.add_option(
        convert, "output_format", str, "png",
        "The output format to convert to (Defaults to png)",
        aliases=["png"],
    )
    common.add_option(
        convert, "outdir", str, "",
        "Output directory to place converted textures. By default, the output texture will be placed next "
        "to the input texture with the output extension.",
        aliases=["-o"],
    )
    common.add_option(
        convert, "converter", str, "texconv",
        "Path to the converter (texconv or compressonatorcli) to use",
        aliases=["-c"],
    )
    common.add_option(convert, "quiet", bool, False, "Only print errors", aliases=["-q"])
    convert.set_defaults(_handler=lambda ns: inst.convert(
        dds_files=ns.dds_files,
        output_format=ns.output_format,
        outdir=ns.outdir,
        converter=ns.converter,
        quiet=ns.quiet,
    ))
    return group
