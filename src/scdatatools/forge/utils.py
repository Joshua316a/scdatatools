import ctypes
import os
import typing
from pathlib import Path

from scdatatools.p4k import P4KFile
from scdatatools.engine.model_utils import vec3_to_vector


if typing.TYPE_CHECKING:
    from scdatatools.forge import DataCoreBinary


def read_and_seek(dcb, data_type, buffer=None):
    """
    Reads a ctypes Structure from a `buffer`, then seeks the buffer to after the read data.

    :param dcb: The :class:`DataCoreBinary` related to this object. This will be assigned to the `dcb` attribute on the
        newly read :class:`ctypes.Structure`
    :param data_type: A :class:`ctypes` object.
    :param buffer: The
    """
    buffer = buffer or dcb.raw_data
    r = data_type.from_buffer(buffer, buffer.tell())
    setattr(r, "_dcb", dcb)
    buffer.seek(ctypes.sizeof(r), os.SEEK_CUR)
    return r


def geometry_for_record(record, data_root: typing.Union[P4KFile, Path] = None, base=False):
    """Return the primary Geometry associated with the given record.

    :param record: Record to resolve the geometry
    :param base: `bool` whether or not to return the base geometry, or a dict of all tagged version of the geometry
    :param data_root: If provided, resolve to the actual file or P4KInfo of the geometry within the `data_root` which
        can be a `P4K` or `Path`
    """
    if record is None:
        return None

    def _geom_from_geometry_node(geom_node):
        geom_path = geom_node.properties["Geometry"].properties["Geometry"].properties["path"]
        if geom_path:
            geom_path = Path(geom_path).as_posix()
            if isinstance(data_root, Path):
                geom_path = data_root / Path(geom_path)
            elif isinstance(data_root, P4KFile):
                try:
                    geom_path = data_root.getinfo(
                        geom_path if geom_path.casefold().startswith("data") else f"data/{geom_path}"
                    )
                except KeyError:
                    pass
            geom = {geom_node.properties["Tags"]: geom_path}
        else:
            geom = {}

        if base:
            return geom_path

        for sub_geom in geom_node.properties["SubGeometry"]:
            geom.update(_geom_from_geometry_node(sub_geom))
        return geom

    geom = None
    try:
        geom_component = next(
            iter(_ for _ in record.properties.get("Components", []) if _.name == "SGeometryResourceParams")
        )
        geom = _geom_from_geometry_node(geom_component.properties["Geometry"])
    except (StopIteration, KeyError):
        pass
    return geom


def landingpad_size_for_dimensions(dcb: "DataCoreBinary", x, y, z, ground_vehicle=False):
    if not hasattr(dcb, "_landing_pads"):
        lprs = []
        for lp in sorted(
            dcb.search_filename("libs/foundry/records/landingpadsize/landingpadsize*.xml"),
            key=lambda r: r.properties["id"],
        ):
            lprs.append(
                {
                    "name": lp.name,
                    "id": lp.properties["id"],
                    "ship_size": vec3_to_vector(lp.properties["shipSize"]),
                    "ground_vehicle_size": vec3_to_vector(lp.properties["groundVehicleSize"]),
                }
            )
        dcb._landing_pads = lprs

    dim = sorted([x, y, z])

    for lp in dcb._landing_pads:
        size = sorted((lp["ground_vehicle_size"] if ground_vehicle else lp["ship_size"]).values())
        if not any(_ >= size[i] for i, _ in enumerate(dim)):
            break
    return lp
