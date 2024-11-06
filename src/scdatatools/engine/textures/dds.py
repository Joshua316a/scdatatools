import struct
import typing
from pathlib import Path
from io import BytesIO

from PIL import DdsImagePlugin, Image

from scdatatools.p4k import P4KInfo


# Magic ("DDS ")
DDS_MAGIC = 0x20534444

# DDS flags
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PITCH = 0x8
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000
DDSD_DEPTH = 0x800000

# DDS caps
DDSCAPS_COMPLEX = 0x8
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400000

DDSCAPS2_CUBEMAP = 0x200
DDSCAPS2_CUBEMAP_POSITIVEX = 0x400
DDSCAPS2_CUBEMAP_NEGATIVEX = 0x800
DDSCAPS2_CUBEMAP_POSITIVEY = 0x1000
DDSCAPS2_CUBEMAP_NEGATIVEY = 0x2000
DDSCAPS2_CUBEMAP_POSITIVEZ = 0x4000
DDSCAPS2_CUBEMAP_NEGATIVEZ = 0x8000
DDSCAPS2_VOLUME = 0x200000

# Pixel Format
DDPF_ALPHAPIXELS = 0x1
DDPF_ALPHA = 0x2
DDPF_FOURCC = 0x4
DDPF_PALETTEINDEXED8 = 0x20
DDPF_RGB = 0x40
DDPF_LUMINANCE = 0x20000


# dds.h

DDS_FOURCC = DDPF_FOURCC
DDS_RGB = DDPF_RGB
DDS_RGBA = DDPF_RGB | DDPF_ALPHAPIXELS
DDS_LUMINANCE = DDPF_LUMINANCE
DDS_LUMINANCEA = DDPF_LUMINANCE | DDPF_ALPHAPIXELS
DDS_ALPHA = DDPF_ALPHA
DDS_PAL8 = DDPF_PALETTEINDEXED8

DDS_HEADER_FLAGS_TEXTURE = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
DDS_HEADER_FLAGS_MIPMAP = DDSD_MIPMAPCOUNT
DDS_HEADER_FLAGS_VOLUME = DDSD_DEPTH
DDS_HEADER_FLAGS_PITCH = DDSD_PITCH
DDS_HEADER_FLAGS_LINEARSIZE = DDSD_LINEARSIZE

DDS_HEIGHT = DDSD_HEIGHT
DDS_WIDTH = DDSD_WIDTH

DDS_SURFACE_FLAGS_TEXTURE = DDSCAPS_TEXTURE
DDS_SURFACE_FLAGS_MIPMAP = DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
DDS_SURFACE_FLAGS_CUBEMAP = DDSCAPS_COMPLEX

DDS_CUBEMAP_POSITIVEX = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEX
DDS_CUBEMAP_NEGATIVEX = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_NEGATIVEX
DDS_CUBEMAP_POSITIVEY = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEY
DDS_CUBEMAP_NEGATIVEY = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_NEGATIVEY
DDS_CUBEMAP_POSITIVEZ = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEZ
DDS_CUBEMAP_NEGATIVEZ = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_NEGATIVEZ


# DXT1
DXT1_FOURCC = 0x31545844

# DXT3
DXT3_FOURCC = 0x33545844

# DXT5
DXT5_FOURCC = 0x35545844


# dxgiformat.h

DXGI_FORMAT_R8G8B8A8_TYPELESS = 27
DXGI_FORMAT_R8G8B8A8_UNORM = 28
DXGI_FORMAT_R8G8B8A8_UNORM_SRGB = 29
DXGI_FORMAT_BC5_TYPELESS = 82
DXGI_FORMAT_BC5_UNORM = 83
DXGI_FORMAT_BC5_SNORM = 84
DXGI_FORMAT_BC6H_UF16 = 95
DXGI_FORMAT_BC6H_SF16 = 96
DXGI_FORMAT_BC7_TYPELESS = 97
DXGI_FORMAT_BC7_UNORM = 98
DXGI_FORMAT_BC7_UNORM_SRGB = 99


class SCDdsImageFile(DdsImagePlugin.DdsImageFile):
    def _open(self):
        if not DdsImagePlugin._accept(self.fp.read(4)):
            msg = "not a DDS file"
            raise SyntaxError(msg)
        (header_size,) = struct.unpack("<I", self.fp.read(4))
        if header_size != 124:
            msg = f"Unsupported header size {repr(header_size)}"
            raise OSError(msg)
        header_bytes = self.fp.read(header_size - 4)
        if len(header_bytes) != 120:
            msg = f"Incomplete header: {len(header_bytes)} bytes"
            raise OSError(msg)
        header = BytesIO(header_bytes)

        flags, height, width = struct.unpack("<3I", header.read(12))
        self._size = (width, height)
        self._mode = "RGBA"

        pitch, depth, mipmaps = struct.unpack("<3I", header.read(12))
        struct.unpack("<11I", header.read(44))  # reserved

        # pixel format
        pfsize, pfflags = struct.unpack("<2I", header.read(8))
        fourcc = header.read(4)
        (bitcount,) = struct.unpack("<I", header.read(4))
        masks = struct.unpack("<4I", header.read(16))
        if pfflags & DDPF_LUMINANCE:
            # Texture contains uncompressed L or LA data
            if pfflags & DDPF_ALPHAPIXELS:
                self._mode = "LA"
            else:
                self._mode = "L"

            self.tile = [("raw", (0, 0) + self.size, 0, (self._mode, 0, 1))]
        elif pfflags & DDPF_RGB:
            # Texture contains uncompressed RGB data
            masks = {mask: ["R", "G", "B", "A"][i] for i, mask in enumerate(masks)}
            rawmode = ""
            if pfflags & DDPF_ALPHAPIXELS:
                rawmode += masks[0xFF000000]
            else:
                self._mode = "RGB"
            rawmode += masks[0xFF0000] + masks[0xFF00] + masks[0xFF]

            self.tile = [("raw", (0, 0) + self.size, 0, (rawmode[::-1], 0, 1))]
        else:
            data_start = header_size + 4
            n = 0
            if fourcc == b"DXT1":
                self.pixel_format = "DXT1"
                n = 1
            elif fourcc == b"DXT3":
                self.pixel_format = "DXT3"
                n = 2
            elif fourcc == b"DXT5":
                self.pixel_format = "DXT5"
                n = 3
            elif fourcc == b"ATI1":
                self.pixel_format = "BC4"
                n = 4
                self._mode = "L"
            elif fourcc == b"ATI2":
                self.pixel_format = "BC5"
                n = 5
                self._mode = "RGB"
            elif fourcc == b"BC5S":
                self.pixel_format = "BC5S"
                n = 5
                self._mode = "RGB"
            elif fourcc == b"DX10":
                data_start += 20
                # ignoring flags which pertain to volume textures and cubemaps
                (dxgi_format,) = struct.unpack("<I", self.fp.read(4))
                self.fp.read(16)
                if dxgi_format in (DXGI_FORMAT_BC5_TYPELESS, DXGI_FORMAT_BC5_UNORM):
                    self.pixel_format = "BC5"
                    n = 5
                    self._mode = "RGB"
                elif dxgi_format == DXGI_FORMAT_BC5_SNORM:
                    self.pixel_format = "BC5S"
                    n = 5
                    self._mode = "RGBA"
                elif dxgi_format == DXGI_FORMAT_BC6H_UF16:
                    self.pixel_format = "BC6H"
                    n = 6
                    self._mode = "RGB"
                elif dxgi_format == DXGI_FORMAT_BC6H_SF16:
                    self.pixel_format = "BC6HS"
                    n = 6
                    self._mode = "RGB"
                elif dxgi_format in (DXGI_FORMAT_BC7_TYPELESS, DXGI_FORMAT_BC7_UNORM):
                    self.pixel_format = "BC7"
                    n = 7
                elif dxgi_format == DXGI_FORMAT_BC7_UNORM_SRGB:
                    self.pixel_format = "BC7"
                    self.info["gamma"] = 1 / 2.2
                    n = 7
                elif dxgi_format in (
                    DXGI_FORMAT_R8G8B8A8_TYPELESS,
                    DXGI_FORMAT_R8G8B8A8_UNORM,
                    DXGI_FORMAT_R8G8B8A8_UNORM_SRGB,
                ):
                    self.tile = [("raw", (0, 0) + self.size, 0, ("RGBA", 0, 1))]
                    if dxgi_format == DXGI_FORMAT_R8G8B8A8_UNORM_SRGB:
                        self.info["gamma"] = 1 / 2.2
                    return
                else:
                    msg = f"Unimplemented DXGI format {dxgi_format}"
                    raise NotImplementedError(msg)
            else:
                msg = f"Unimplemented pixel format {repr(fourcc)}"
                raise NotImplementedError(msg)

            self.tile = [("bcn", (0, 0) + self.size, data_start, (n, self.pixel_format))]


Image.register_open(SCDdsImageFile.format, SCDdsImageFile, DdsImagePlugin._accept)
Image.register_extension(SCDdsImageFile.format, ".dds")


class DDSNotSplit(Exception):
    pass


def is_glossmap(dds_filename: typing.Union[Path, str]) -> bool:
    return str(dds_filename)[-1] == "a"


def is_normals(dds_filename) -> bool:
    return "_ddna" in str(dds_filename)


def unsplit_dds(
    dds_files: typing.Dict[str, typing.Union[P4KInfo, Path, typing.IO, bytes]],
    outfile: typing.Union[Path, str] = "-",
) -> typing.Union[bytes, Path]:
    """
    Unsplit a split `.dds` (or `.dds.a`) texture (a `.dds` with `.dds.N` files next to it where `.N` is a partial piece
    of the `.dds`) into a single, valid `.dds` texture file.

    :param dds_files: `dict` containing all the pieces of a split texture file. The key should be the
        filename of the component, and the value should be a file-like object or bytes of the texture.
    :param outfile: The path of to write the output to. Pass '-' to have the unsplit texture buffer returned directly.
    :return: The recombined bytes if `outfile` is '-', otherwise the `Path` of the output file
    """

    parts = {}
    dds_header = None
    hdr_data = None

    # extract the DDS header from the `.dds` top file
    for n, p in dds_files.items():
        if n.endswith(".dds") or n.endswith(".dds.a"):
            dds_header = n
            hdr_data = p
        else:
            parts[n] = p

    if hdr_data is None:
        raise DDSNotSplit(f'Could not determine the DDS header file from {",".join(dds_files.keys())}')

    if isinstance(hdr_data, (P4KInfo, Path)):
        hdr_data = hdr_data.open("rb").read()
    if not isinstance(hdr_data, bytes):
        hdr_data = hdr_data.read()

    # glossmap's don't have the DDS header... add it so texconv will work
    glossmap = is_glossmap(dds_header)
    if glossmap:
        hdr_data = b"DDS " + hdr_data

    dds_magic, dds_hdr_len = struct.unpack("<4sI", hdr_data[:8])
    dds_hdr_len += 4  # hdr_len does not include the magic bytes
    if dds_magic != b"DDS ":
        raise ValueError("Invalid DDS header")

    if hdr_data[84:88] == b"DX10":
        dds_hdr_len += 20

    dds_file = hdr_data[:dds_hdr_len]
    # unsplit files should be largest to smallest
    for dds in sorted([_ for _ in parts.keys()], reverse=True, key=lambda d: d.split(".")[-1]):
        if is_glossmap(dds) and not glossmap:
            continue
        elif not is_glossmap(dds) and glossmap:
            continue

        if isinstance(parts[dds], (P4KInfo, Path)):
            dds_file += parts[dds].open("rb").read()
        elif isinstance(parts[dds], bytes):
            dds_file += parts[dds]
        else:
            dds_file += parts[dds].read()

    # finally add the remainder of the `.dds` top file, `.dds.0` if you will
    dds_file += hdr_data[dds_hdr_len:]

    if outfile == "-":
        return dds_file

    Path(outfile).parent.mkdir(parents=True, exist_ok=True)
    with open(outfile, "wb") as out:
        out.write(dds_file)
    return Path(outfile)


def collect_parts(dds_file: typing.Union[str, Path, P4KInfo], from_list: typing.List[P4KInfo] = None) -> typing.Dict:
    """Collect all of the component parts of a split dds texture and return them as a dict where the keys are the
    filename and the value is the `P4KInfo` or `Path` of the part.

    :param from_list: Used to provide a sub-list of P4K members when searching the P4K for parts. It should be expected
        that the `from_list` does in fact contain the parts
    """
    if isinstance(dds_file, P4KInfo):
        dds_filename = Path(dds_file.filename)
        basename = (dds_filename.parent / dds_filename.stem.split(".")[0]).with_suffix(".dds").as_posix().casefold()
        if from_list:
            dds_files = {
                p.name: _ for _ in from_list if (p := Path(_.filename)).as_posix().casefold().startswith(basename)
            }
        else:
            dds_files = {Path(_.filename).name: _ for _ in dds_file.p4k.search(basename, mode="startswith")}
    else:
        dds_filename = Path(dds_file)
        basename = dds_file.parent / dds_file.stem.split(".")[0]
        dds_files = {_.name: _ for _ in basename.parent.glob(f"{basename.name}.dds*")}

    if is_glossmap(dds_filename):
        dds_files = {k: v for k, v in dds_files.items() if k.endswith("a")}
    else:
        dds_files = {k: v for k, v in dds_files.items() if not k.endswith("a")}

    return dds_files


def collect_and_unsplit(
    dds_file: typing.Union[str, Path, P4KInfo], outfile="-", remove: bool = False
) -> typing.Union[bytes, Path]:
    """
    Automatically find associated pieces of a split DDS texture and return the recombined (un-split) texture.

    :param dds_file: The path to a piece of a split DDS texture, or the `P4KInfo` of a piece of a split DDS within a
        `p4k` archive.
    :param outfile: The output path for the unsplit texture. Defaults to '-' which will return the bytes of the texture
        instead of writing it to a file
    :param remove: Remove the collected pieces after unsplitting. Must specify an `outfile`, does nothing if '-'.
    :return: Bytes of the recombined texture if `outfile` is '-', otherwise the `Path` to the file that was created
    """
    dds_files = collect_parts(dds_file)
    outfile = unsplit_dds(dds_files, outfile=outfile)

    if isinstance(outfile, Path) and remove:
        if is_glossmap(outfile):
            [_.unlink(missing_ok=True) for _ in outfile.parent.glob(f'{outfile.name.split(".")[0]}.dds.[0-9]a')]
        else:
            [_.unlink(missing_ok=True) for _ in outfile.parent.glob(f'{outfile.name.split(".")[0]}.dds.[0-9]')]

    return outfile
