import typing

from .common import DataCoreObject, register_record_handler


@register_record_handler("VehicleRole")
class VehicleRole(DataCoreObject):
    @property
    def display_name(self) -> str:
        return self.record.properties.get("displayName", "")

    def __repr__(self):
        return f"<VehicleRole id:{self.guid} name:{self.display_name}>"


@register_record_handler("VehicleCareer")
class VehicleCareer(DataCoreObject):
    @property
    def display_name(self) -> str:
        return self.record.properties["displayName"]

    @property
    def roles(self) -> typing.List[VehicleRole]:
        return [VehicleRole(self._datacore, r.reference.id) for r in self.record.properties.get("roleList", [])]
