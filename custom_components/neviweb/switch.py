"""
Support for Neviweb switch.
type 120 = load controller device, RM3250RF and RM3200RF
For more details about this platform, please refer to the documentation at  
https://www.sinopetech.com/en/support/#api
"""
import logging

import voluptuous as vol
import time

import custom_components.neviweb as neviweb
from . import (NeviwebClient, NeviwebDeviceInfo, SCAN_INTERVAL)
from homeassistant.components.switch import (SwitchEntity)
from datetime import timedelta
from homeassistant.helpers import (entity_platform)
from .const import (DOMAIN, ATTR_POWER_MODE, ATTR_INTENSITY, ATTR_RSSI,
    ATTR_WATTAGE, ATTR_WATTAGE_INSTANT, MODE_AUTO, MODE_MANUAL, 
    ATTR_OCCUPANCY_MODE,
    SERVICE_SET_SWITCH_OPERATION_MODE, SERVICE_SET_SWITCH_OCCUPANCY_MODE, 
    SERVICE_SET_OPERATION_MODE_SCHEMA, SERVICE_SET_OCCUPANCY_MODE_SCHEMA)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'neviweb switch'
PARALLEL_UPDATES = 1

UPDATE_ATTRIBUTES = [ATTR_POWER_MODE, ATTR_INTENSITY, ATTR_RSSI, 
    ATTR_WATTAGE, ATTR_WATTAGE_INSTANT, ATTR_OCCUPANCY_MODE]

IMPLEMENTED_DEVICE_TYPES = [120] #power control device

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up neviweb switch."""
    _LOGGER.debug("Entering switch setup_entry")
    data = hass.data[DOMAIN]
    entities = []
    for device in data.devices:
        if device.type in IMPLEMENTED_DEVICE_TYPES:
            entities.append(NeviwebSwitch(data.neviweb_client, device))
            
    async_add_entities(entities, True)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_SWITCH_OPERATION_MODE,
        SERVICE_SET_OPERATION_MODE_SCHEMA,
        "async_set_operation_mode",
    )

    platform.async_register_entity_service(
        SERVICE_SET_SWITCH_OCCUPANCY_MODE,
        SERVICE_SET_OCCUPANCY_MODE_SCHEMA,
        "async_set_occupancy_mode",
    )

class NeviwebSwitch(SwitchEntity):
    """Implementation of a Neviweb switch."""

    def __init__(self, client: NeviwebClient, device: NeviwebDeviceInfo):
        """Initialize."""
        self._device = device
        self._client = client
        self._wattage = 0 # keyCheck("wattage", device_info, 0, name)
        self._brightness = 0
        self._operation_mode = 1
        self._current_power_w = None
        self._today_energy_kwh = None
        self._rssi = None
        self._occupancy = None
        _LOGGER.debug("Setting up switch %s", self._device.name)

    async def async_update(self):
        """Get the latest data from Neviweb and update the state."""
        start = time.time()
        device_data = await self._client.async_get_device_attributes(
            self.unique_id, UPDATE_ATTRIBUTES)
        device_daily_stats = await self._client.async_get_device_daily_stats(
            self.unique_id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._device.name, elapsed, device_data)
        if "error" not in device_data:
            if "errorCode" not in device_data:
                self._brightness = device_data[ATTR_INTENSITY] if \
                    device_data[ATTR_INTENSITY] is not None else 0.0
                self._operation_mode = device_data[ATTR_POWER_MODE] if \
                    device_data[ATTR_POWER_MODE] is not None else MODE_MANUAL
                #self._alarm = device_data["alarm"]
                self._current_power_w = device_data[ATTR_WATTAGE_INSTANT]["value"]
                self._wattage = device_data[ATTR_WATTAGE]["value"]
                self._rssi = device_data[ATTR_RSSI]
                self._occupancy = device_data[ATTR_OCCUPANCY_MODE]
                self._today_energy_kwh = device_daily_stats[0] / 1000 if \
                    device_daily_stats[0] is not None else 0
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
            "via_device": (DOMAIN, self._device.parent_id)
        }

    @property  
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._brightness != 0

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.async_set_brightness(self.unique_id, 100)
        
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.async_set_brightness(self.unique_id, 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'operation_mode': self.operation_mode,
                'rssi': self._rssi,
                'occupancy': self._occupancy,
                'wattage': self._wattage}
       
    @property
    def operation_mode(self):
        return self._operation_mode

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._current_power_w

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return self._today_energy_kwh
    
    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._current_power_w == 0

    async def async_set_operation_mode(self, operation_mode):
        _LOGGER.debug("async_set_operation_mode %s for %s ", operation_mode,
            self._device.name)
        await self._client.async_set_operation_mode(self.unique_id, operation_mode)

    async def async_set_occupancy_mode(self, occupancy_mode):
        _LOGGER.debug("async_set_occupancy_mode %s for %s ", occupancy_mode,
            self._device.name)
        await self._client.async_set_occupancy_mode(self.unique_id, occupancy_mode)
