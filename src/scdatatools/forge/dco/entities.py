import typing
import logging
from math import prod
from functools import cached_property

from scdatatools.forge.dftypes import GUID, Record
from scdatatools.engine.constants import SCU_SIZE_M3
from scdatatools.forge.utils import landingpad_size_for_dimensions
from scdatatools.engine.model_utils import vec3_to_vector, Vector3D
from scdatatools.engine.cryxml import dict_from_cryxml_file
from scdatatools.utils import generate_free_key

from .common import DataCoreRecordObject, register_record_handler, dco_from_datacore, register_strong_pointer_handler
from .vehicle import VehicleRole
from .common import DataCoreObject, dco_from_guid


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from scdatatools.sc import StarCitizen


@register_record_handler("EntityClassDefinition")
class Entity(DataCoreRecordObject):
    def __init__(self, sc: "StarCitizen", guid_or_dco: typing.Union[str, GUID, Record]):
        super().__init__(sc, guid_or_dco)

        self.components = {}
        for c in sorted(self.object.properties["Components"], key=lambda _: _.name):
            self.components[generate_free_key(c.name, self.components.keys())] = dco_from_datacore(self._sc, c)
        self.tags = [dco_from_datacore(self._sc, t) for t in self.object.properties["tags"] if t.name]
        self.geom_hash = None

    @property
    def label(self):
        try:
            key_label = (
                self.components["SAttachableComponentParams"]
                .properties["AttachDef"]
                .properties["Localization"]
                .properties["Name"][1:]
            )
            label = self._sc.localization.gettext(key_label)
            return label
        except:
            return None


@register_strong_pointer_handler("SEntityComponentDefaultLoadoutParams")
class SEntityDefaultLoadoutParams(DataCoreObject):
    @cached_property
    def loadout(self):
        def proc_loadout(entries):
            lo = {}
            for entry in entries:
                try:
                    entity = entry.properties["entityClassName"]
                    sublo = entry.properties.get("loadout", {})
                    if sublo:
                        sublo = proc_loadout(sublo.properties.get("entries", []))
                    if ac := self._sc.attachable_component_manager.attachable_components.get(entity):
                        entity = ac
                        if hasattr(entity, "set_loadout"):
                            entity.set_loadout(sublo)
                    port_name = entry.properties["itemPortName"]
                    lo[port_name] = {"entity": entity, "loadout": sublo}
                except Exception as e:
                    logger.exception(
                        "processing component SEntityComponentDefaultLoadoutParams",
                        exc_info=e,
                    )
            return lo

        return proc_loadout(self.properties["loadout"].properties.get("entries", []))


class Vehicle(Entity):
    @property
    def category(self) -> str:
        return self.record.properties.get("Category", "")

    @property
    def icon(self) -> str:
        return self.record.properties.get("Icon", "")

    @property
    def invisible(self) -> bool:
        return self.record.properties.get("Invisible", False)

    @property
    def bbox_selection(self) -> bool:
        return self.record.properties.get("BBoxSelection", False)

    @property
    def lifetime_policy(self) -> typing.Union[DataCoreObject, None]:
        try:
            return dco_from_guid(self._datacore, self.record.properties["lifetimePolicy"])
        except KeyError:
            return None

    @property
    def object_containers(self) -> typing.Dict[str, object]:
        try:
            return self.components["VehicleComponentParams"].properties["objectContainers"]
        except KeyError:
            return {}

    @property
    def max_bounding_box_size(self) -> typing.Union[Vector3D, None]:
        try:
            return vec3_to_vector(self.components["VehicleComponentParams"].properties["maxBoundingBoxSize"].properties)
        except KeyError:
            return None

    @cached_property
    def vehicle_definition(self):
        try:
            vd = self._sc.p4k.NameToInfoLower[
                "data/" + self.components["VehicleComponentParams"].vehicleDefinition.lower()
            ]
            with vd.open() as f:
                return dict_from_cryxml_file(f)
        except Exception as e:
            logger.exception(f"Failed to read vehicle definition for {self.object.filename}", exc_info=e)
        return {}

    @property
    def mass(self) -> float:
        return float(self.vehicle_definition["Vehicle"]["Parts"]["Part"]["@mass"])

    @property
    def parts(self):
        # Make a little cleaner to navigate parts dict
        p = self.vehicle_definition["Vehicle"]["Parts"]["Part"].copy()
        p["parts"] = {}

        def _walk_parts(d, parts):
            if not isinstance(parts, list):
                parts = [parts]
            for p in parts:
                n = p["@name"]
                d[n] = p.copy()
                if "Parts" in p:
                    del d[n]["Parts"]
                    d[n]["parts"] = {}
                    _walk_parts(d[n]["parts"], p["Parts"]["Part"])

        _walk_parts(p["parts"], p["Parts"]["Part"])
        del p["Parts"]
        return p

    @cached_property
    def hardpoints(self):
        hps = {}

        def _walk_parts(d):
            if isinstance(d, list):
                for part in d:
                    _walk_parts(part)
            else:
                if "hardpoint" in (name := d.get("@name", "")).lower() and d.get("@class", "") == "ItemPort":
                    hps[name] = d
                _walk_parts(d.get("Part" if "Part" in d else "Parts", []))

        _walk_parts(self.vehicle_definition.get("Vehicle", {}).get("Parts", []))
        return hps

    @cached_property
    def editable_hardpoints(self):
        return {k: v for k, v in self.hardpoints.items() if "uneditable" not in v.get("ItemPort", {}).get("@flags", "")}

    @cached_property
    def default_loadout(self):
        dl = self.components["SEntityComponentDefaultLoadoutParams"].loadout.copy()

        def _walk_loadout(dl):
            for v in dl.values():
                if v.get("entity"):
                    if e := self._datacore.entities.get(v["entity"], ""):
                        v["entity"] = dco_from_datacore(self._sc, e)
                if v.get("loadout", []):
                    _walk_loadout(v["loadout"])

        _walk_loadout(dl)
        return dl


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/entities/spaceships/.*",
)
class Ship(Vehicle):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vd = {}

    @cached_property
    def item_ports(self) -> typing.Dict[str, dict]:
        ips = {}

        def parse_loadout(parent, loadout):
            if loadout is None:
                return
            for entry in loadout.properties.get("entries", []):
                parent[entry.properties["itemPortName"]] = {
                    "entity_class_name": entry.properties["entityClassName"],
                    "inventory_container": entry.properties["inventoryContainer"],
                    "item_port_name": entry.properties["itemPortName"],
                    "loadout": {},
                }
                parse_loadout(parent[entry.properties["itemPortName"]]["loadout"], entry.properties["loadout"])

        parse_loadout(ips, self.components["SEntityComponentDefaultLoadoutParams"].properties["loadout"])
        return ips

    @property
    def crew_size(self) -> int:
        try:
            return self.components["VehicleComponentParams"].properties["crewSize"]
        except KeyError:
            return 0

    @property
    def vehicle_name(self) -> str:
        return self.components["VehicleComponentParams"].properties.get("vehicleName", "")

    @property
    def vehicle_role(self) -> typing.Union[VehicleRole, None]:
        try:
            return VehicleRole(self._datacore, self.components["VehicleComponentParams"].properties["vehicleRoleRef"])
        except KeyError:
            return None

    @property
    def vehicle_description(self) -> str:
        return self.components["VehicleComponentParams"].properties.get("vehicleDescription", "")

    @property
    def vehicle_image_path(self) -> str:
        return self.components["VehicleComponentParams"].properties.get("vehicleName", "")

    @property
    def vehicle_career(self):
        try:
            return dco_from_guid(
                self._datacore, self.components["VehicleComponentParams"].properties["vehicleCareerRef"].value
            )
        except KeyError:
            return None

    @property
    def is_gravlev(self) -> bool:
        return self.components["VehicleComponentParams"].properties["isGravlevVehicle"]

    @property
    def dogfight_enabled(self) -> bool:
        return self.components["VehicleComponentParams"].properties["dogfightEnabled"]

    @cached_property
    def cargo(self) -> dict:
        grids = {}
        total = 0
        for name, ip in self.item_ports.items():
            if entity_record := self._datacore.entities.get(ip["entity_class_name"]):
                entity = Entity(self._datacore, entity_record)
                if "SCItemCargoGridParams" in entity.components:
                    grids[name] = entity
                    total += prod(
                        entity.components["SCItemCargoGridParams"].properties["dimensions"].properties.values()
                    )
        return {"scu": total / SCU_SIZE_M3, "grids": grids}

    @cached_property
    def landingpad_size(self):
        return landingpad_size_for_dimensions(self._datacore, **self.max_bounding_box_size)

    def __repr__(self):
        return f"<DCO Ship {self.name}>"

    @property
    def scm_speed(self) -> float:
        return float(self.vehicle_definition["Vehicle"]["MovementParams"]["Spaceship"][""])


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/entities/groundvehicles/.*",
)
class GroundVehicle(Vehicle):
    def __repr__(self):
        return f"<DCO GroundVehicle {self.name}>"


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/entities/scitem/.*",
)
class Carryable(Entity):
    def __init__(self, datacore, guid):
        super().__init__(datacore, guid)
        try:
            geom = self.components["SGeometryResourceParams"].object.properties["Geometry"].properties["Geometry"]
            self.geometry_path = geom.properties["Geometry"].properties["path"]
            self.geom_hash = hash(self.geometry_path)
        except:
            self.geometry_path = None

    def __repr__(self):
        return f"<DCO Carryable {self.name} '{self.label}'>"


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/entities/scitem/characters/.*",
)
class Crateable(Carryable):
    def __init__(self, datacore, guid):
        super().__init__(datacore, guid)
        try:
            subs = self.components["SGeometryResourceParams"].object.properties["Geometry"].properties["SubGeometry"]
            self.sub_geometry_path = [x.properties["Geometry"].properties["Geometry"].properties.path for x in subs]
            self.geom_hash = hash("".join(self.sub_geometry_path))
        except:
            self.sub_geometry_path = []

    def __repr__(self):
        return f"<DCO Crateable {self.name} '{self.label}'>"


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/entities/scitem/ships/weapon_mounts/gimbal/.*",
)
class GimbalMount(Entity):
    def __repr__(self):
        return f"<GimbalMount {self.name}>"


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/transitsystem/transitcarriage/.*",
)
class TransitCarriage(Entity):
    def __repr__(self):
        return f"<TransitCarriage {self.name}>"


@register_record_handler(
    "EntityClassDefinition", filename_match="libs/foundry/records/entities/scitem/ships/thrusters/*"
)
class ShipThruster(Entity):
    def __repr__(self):
        return f"<ShipThruster {self.name}>"
