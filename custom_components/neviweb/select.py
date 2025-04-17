import logging
import asyncio

import voluptuous as vol
import time

from homeassistant.components.select import SelectEntity

from datetime import timedelta

import custom_components.neviweb as neviweb
from . import (
    NeviwebClient,
    NeviwebDeviceInfo,
    SCAN_INTERVAL,
)
from .const import (
    DOMAIN,
    MODE_AUTO,
    MODE_MANUAL,
    ATTR_POWER_MODE,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

IMPLEMENTED_POWER_MODE_SKU = ["RM3200RF", "RM3250RF"]
IMPLEMENTED_OCCUPANCY_MODE_SKU = ["RM3200RF", "RM3250RF"]

UPDATE_ATTRIBUTES_POWER_MODE = [ATTR_POWER_MODE]

async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.debug("Entering select setup_entry")
    data = hass.data[DOMAIN]
    entities = []
    for device in data.devices:
        if device.sku in IMPLEMENTED_POWER_MODE_SKU:
            entities.append(NeviwebSelect(data.neviweb_client, device))

    async_add_entities(entities, True)


class NeviwebSelect(SelectEntity):

    def __init__(self, client: NeviwebClient, device: NeviwebDeviceInfo):
        """Initialize."""
        self._device = device
        self._client = client
        self._attr_current_option = None
        self._attr_options = [MODE_AUTO, MODE_MANUAL]

    @property
    def unique_id(self):
        """Return unique ID based on Neviweb device ID."""
        return self._device.id

    @property
    def name(self):
        """Return the name of the switch."""
        return self._device.formatted_name

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self.unique_id),
                (DOMAIN, self._device.identifier)
            },
            "name": self._device.name,
            "manufacturer": self._device.vendor,
            "model": self._device.sku,
            "sw_version": self._device.software_version,
            "suggested_area": self._device.group.name,
            "via_device": (DOMAIN, self._device.parent_id),
            "configuration_url": self._device.configuration_url
        }

    # @property
    # def options(self) -> list[str]:
    #     """Return a set of selectable options."""
    #     return [MODE_AUTO, MODE_MANUAL]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._client.async_set_operation_mode(self.unique_id, option)

    async def async_update(self):
        """Get the latest data from Neviweb and update the state."""
        start = time.time()
        device_data = await self._client.async_get_device_attributes(
            self.unique_id, UPDATE_ATTRIBUTES_POWER_MODE)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._device.name, elapsed, device_data)
        if "error" not in device_data:
            if "errorCode" not in device_data:
                self._attr_current_option = device_data[ATTR_POWER_MODE] if \
                    device_data[ATTR_POWER_MODE] is not None else MODE_MANUAL
                return
            else:
                if device_data["errorCode"] == "ReadTimeout":
                    _LOGGER.warning("Error in reading device %s: (%s), too slow to respond or busy.", self._device.name, device_data)
                else:
                    _LOGGER.warning("Unknown errorCode, device: %s, error: %s", self._device.name, device_data)
            return
        else:
            if device_data["error"]["code"] == "DVCCOMMTO":
                _LOGGER.warning("Cannot update %s: %s. Device is busy or does not respond quickly enough.", self._device.name, device_data)
            elif device_data["error"]["code"] == "SVCINVREQ":
                _LOGGER.warning("Invalid or malformed request to Neviweb, %s:",  device_data)
            elif device_data["error"]["code"] == "DVCACTNSPTD":
                _LOGGER.warning("Device action not supported, %s:",  device_data)
            elif device_data["error"]["code"] == "DVCUNVLB":
                _LOGGER.warning("Device %s unavailable, Neviweb maintnance update, %s:", self._device.name, device_data)
            elif device_data["error"]["code"] == "SVCERR":
                _LOGGER.warning("Device %s statistics unavailables, %s:", self._device.name, device_data)
            else:
                _LOGGER.warning("Unknown error, device: %s, error: %s", self._device.name, device_data)
