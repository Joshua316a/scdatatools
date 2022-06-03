import typing
from math import prod
from functools import cached_property

from .vehicle import VehicleRole
from .common import DataCoreObject, register_record_handler, dco_from_guid

from scdatatools.engine.constants import SCU_SIZE_M3
from scdatatools.forge.utils import landingpad_size_for_dimensions
from scdatatools.engine.model_utils import vec3_to_vector, Vector3D
from scdatatools.engine.cryxml import is_cryxmlb_file, etree_from_cryxml_file, dict_from_cryxml_file


if typing.TYPE_CHECKING:
    from scdatatools.p4k import P4KFile


@register_record_handler("EntityClassDefinition")
class Entity(DataCoreObject):
    def __init__(self, datacore, guid):
        super().__init__(datacore, guid)

        self.components = {}
        for c in sorted(self.record.properties["Components"], key=lambda c: c.name):
            if c.name in self.components:
                print(
                    f"WARNING: Duplicate component for entity, shouldnt be possible? {c.name}"
                )
                continue
            self.components[c.name] = c
        self.tags = [
            dco_from_guid(self._datacore, t.name)
            for t in self.record.properties["tags"]
            if t.name
        ]


@register_record_handler(
    "EntityClassDefinition",
    filename_match="libs/foundry/records/entities/spaceships/.*",
)
class Ship(Entity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vd = {}

    @cached_property
    def item_ports(self) -> typing.Dict[str, dict]:
        ips = {}

        def parse_loadout(parent, loadout):
            if loadout is None:
                return
            for entry in loadout.properties.get('entries', []):
                parent[entry.properties['itemPortName']] = {
                    'entity_class_name': entry.properties['entityClassName'],
                    'inventory_container': entry.properties['inventoryContainer'],
                    'item_port_name': entry.properties['itemPortName'],
                    'loadout': {}
                }
                parse_loadout(parent[entry.properties['itemPortName']]['loadout'], entry.properties['loadout'])

        parse_loadout(ips, self.components["SEntityComponentDefaultLoadoutParams"].properties['loadout'])
        return ips

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
    def bbox_size(self) -> typing.Union[Vector3D, None]:
        try:
            return vec3_to_vector(self.components["VehicleComponentParams"].properties["maxBoundingBoxSize"].properties)
        except KeyError:
            return None

    def vehicle_definition(self, p4k: "P4KFile", mode='dict'):
        """ Return the converted CryXmlB vehicle definition from the given `P4KFile`.

        :param p4k: `P4KFile` to read the vehicle definition from
        :param mode: `dict` to convert the cryxmlb to a dict, or `etree` to convert to an ElementTree
        """
        mode = mode.casefold()
        if vd := self._vd.get('mode'):
            return vd

        def_info = p4k.NameToInfoLower.get(
            f'data/' + self.components["VehicleComponentParams"].properties['vehicleDefinition'].lower()
        )
        if def_info is not None:
            with def_info.open() as def_file:
                if is_cryxmlb_file(def_file):
                    if mode == 'dict':
                        self._vd[mode] = dict_from_cryxml_file(def_file)
                    else:
                        self._vd[mode] = etree_from_cryxml_file(def_file)
                    return self._vd[mode]
        return None

    @property
    def crew_size(self) -> int:
        try:
            return self.components["VehicleComponentParams"].properties['crewSize']
        except KeyError:
            return 0

    @property
    def vehicle_name(self) -> str:
        return self.components["VehicleComponentParams"].properties.get('vehicleName', '')

    @property
    def vehicle_role(self) -> typing.Union[VehicleRole, None]:
        try:
            return VehicleRole(self._datacore, self.components["VehicleComponentParams"].properties['vehicleRoleRef'])
        except KeyError:
            return None

    @property
    def vehicle_description(self) -> str:
        return self.components["VehicleComponentParams"].properties.get('vehicleDescription', '')

    @property
    def vehicle_image_path(self) -> str:
        return self.components["VehicleComponentParams"].properties.get('vehicleName', '')

    @property
    def vehicle_career(self):
        try:
            return dco_from_guid(self._datacore,
                                 self.components["VehicleComponentParams"].properties['vehicleCareerRef'].value)
        except KeyError:
            return None

    @property
    def is_gravlev(self) -> bool:
        return self.components["VehicleComponentParams"].properties['isGravlevVehicle']

    @property
    def dogfight_enabled(self) -> bool:
        return self.components["VehicleComponentParams"].properties['dogfightEnabled']

    @cached_property
    def cargo(self) -> dict:
        grids = {}
        total = 0
        for name, ip in self.item_ports.items():
            if entity_record := self._datacore.entities.get(ip['entity_class_name']):
                entity = Entity(self._datacore, entity_record)
                if "SCItemCargoGridParams" in entity.components:
                    grids[name] = entity
                    total += prod(
                        entity.components["SCItemCargoGridParams"].properties["dimensions"].properties.values()
                    )
        return {'scu': total / SCU_SIZE_M3, 'grids': grids}

    @cached_property
    def landingpad_size(self):
        return landingpad_size_for_dimensions(self._datacore, **self.bbox_size)

    def __repr__(self):
        return f"<DCO Ship {self.name}>"
