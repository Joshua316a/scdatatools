import io
import typing
import logging
from pathlib import Path
import concurrent.futures

from PIL import Image

from scdatatools import plugins
from scdatatools.p4k import P4KInfo, monitor_msg_from_info
from scdatatools.utils import NamedBytesIO
from . import dds

logger = logging.getLogger(__name__)


def convert_buffer(
    inbuf: bytes,
    out_format: str = "default",
) -> (bytes, str):
    """
    Converts a buffer `inbuf` to the output format `out_format`. See :func:convert for more information on parameters

    :param inbuf: Bytes of the texture to convert
    :param out_format: The desired output format. Default's to the default output format for the platform, 'default'
    :return: Tuple containing the `bytes` of the converted image in the specified `output_format` and the `str` format
        of the returned `bytes`
    """

    out_format = "tif" if out_format == "default" else out_format
    out_format = out_format.replace(".", "")

    with Image.open(io.BytesIO(inbuf)) as img:
        with io.BytesIO() as output:
            img.save(output, format=out_format.upper())
            tex = output.getvalue()

    return tex, out_format


def tex_convert(
    infile: typing.Union[str, Path, io.BufferedIOBase, io.RawIOBase, NamedBytesIO],
    outfile: typing.Union[str, Path],
    overwrite: bool = False,
) -> Path:
    """Convert the texture file provided by `infile` to `outfile` using the an external converter. By default, this
    will attempt to use `texconv`. If that fails, or isn't available, then it'll attempt to use `compressonatorcli`.
    Setting `converter` explicitly will disable this behavior and only attempt the chosen `converter`.

    The output format is determined from the extension of `outfile`

    :param infile:  A `str`, `Path`, file-like object or bytes of the input texture
    :param outfile:  The output file path. Glossmaps will alter the output filename. Be sure to check the returned
        path if necessary.
    :param overwrite: Overwrite `outfile` if it already exists
    :raises:
        ConversionError: If the converter does not exit cleanly. Output from the converter will be supplied
        ConverterUnavailable: If the specified `converter_bin` is invalid, or if `texconv` or `compressonatorcli`
            cannot be found on the system's `PATH`
    :return: :class:`Path` of the converted image if successful
    """
    if isinstance(outfile, str):
        outfile = Path(outfile)
    if outfile.exists():
        if overwrite:
            outfile.unlink()
        else:
            raise ValueError(f'outfile "{outfile}" already exists')

    with Image.open(infile) as img:
        img.save(outfile)
        return outfile


@plugins.register
class DDSTextureConverter(plugins.P4KConverterPlugin):
    name = "ddstexture_converter"
    display_name = "DDS Converter"
    handles = [".dds"]

    @classmethod
    def convert(
        cls,
        members: typing.List["P4KInfo"],
        path: typing.Union[Path, str],
        overwrite: bool = False,
        save_to: bool = False,
        options: typing.Dict = None,
        monitor: typing.Callable = None,
    ) -> typing.Tuple[typing.List["P4KInfo"], typing.List[Path]]:
        options = options or {}
        output_fmt = options.get("ddstexture_converter_fmt", "dds").casefold()

        if output_fmt == "dds" and not options.get("ddstexture_converter_unsplit", False):
            # output dds and unsplit not checked, do nothing
            return members, []

        replace = options.get("ddstexture_converter_replace", False)

        unhandled_members = []
        extracted_paths = []
        to_convert = []
        while members:
            f = members[-1]  # collect_parts needs the file to be in the list, so pop it later, -1 since we're popping
            if ".dds" not in f.filename.casefold():
                unhandled_members.append(members.pop())
            else:
                parts = dds.collect_parts(f, from_list=members)
                outpath = cls.outpath(path, next(iter(parts.values())), save_to)
                is_glossmap = dds.is_glossmap(outpath)

                out_name = outpath.name.split(".", maxsplit=1)[0]
                if is_glossmap:
                    out_name += ".glossmap"

                outdds = outpath.with_name(out_name + (".dds.a" if is_glossmap else ".dds"))
                if output_fmt == "dds":
                    outpath = outdds
                else:
                    outpath = outpath.with_name(f"{out_name}.{output_fmt}")

                for info in parts.values():
                    members.remove(info)

                if overwrite or not outdds.is_file():
                    if not overwrite and outpath.is_file() and replace:
                        continue  # texture was already converted and we would get rid of the dds, skip
                    try:
                        # only unsplit
                        dds.unsplit_dds(parts, outdds)
                        if monitor is not None:
                            dds_header = [_ for _ in parts if _.endswith(".dds") or _.endswith(".dds.a")][0]
                            monitor(monitor_msg_from_info(parts[dds_header]))

                        if output_fmt != "dds":
                            to_convert.append((outdds, outpath))
                        extracted_paths.append(outpath.as_posix())
                    except Exception:
                        logger.exception("Failed to un-split texture")
                        # re-add the parts to the unhandled so they at least get exported
                        for info in parts.values():
                            unhandled_members.append(info)

        def _do_convert(tex_in, tex_out):
            try:
                out = tex_convert(
                    infile=tex_in,
                    outfile=tex_out,
                    overwrite=overwrite,
                )
                if replace:
                    tex_in.unlink()
            except Exception as e:
                return tex_in, str(e)
            return out, ""

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for conv in to_convert:
                futures.append(executor.submit(_do_convert, tex_in=conv[0], tex_out=conv[1]))
            for future in concurrent.futures.as_completed(futures):
                if monitor is not None:
                    out, error = future.result()
                    if error:
                        monitor(f"failed to convert {out}: {error}")
                    else:
                        extracted_paths.append(out.as_posix())
                        monitor(f"converted {out}")

        return unhandled_members, extracted_paths
