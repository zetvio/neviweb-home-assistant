"""
Support for Neviweb switch.
type 120 = load controller device, RM3250RF and RM3200RF
For more details about this platform, please refer to the documentation at
https://www.sinopetech.com/en/support/#api
"""
import logging
import asyncio

import voluptuous as vol
import time

from homeassistant.const import (
    STATE_ON,
    STATE_OFF
)
from homeassistant.components.switch import (
    SwitchEntity,
    SwitchDeviceClass
)
from datetime import timedelta
from homeassistant.helpers import (entity_platform)

import custom_components.neviweb as neviweb
from . import (
    NeviwebClient,
    NeviwebDeviceInfo,
    SCAN_INTERVAL,
)
from .const import (
    DOMAIN,
    ATTR_INTENSITY,
    ATTR_MOTOR_POSITION,
    ATTR_MOTOR_TARGET_POSITION,
    ATTR_OCCUPANCY_MODE,
    ATTR_ONOFF,
    ATTR_POWER_MODE,
    ATTR_RSSI,
    ATTR_WATTAGE,
    ATTR_WATTAGE_INSTANT,
    # MODE_AUTO,
    MODE_MANUAL,
    SERVICE_SET_SWITCH_OPERATION_MODE,
    SERVICE_SET_SWITCH_OCCUPANCY_MODE,
    SERVICE_SET_OPERATION_MODE_SCHEMA,
    SERVICE_SET_OCCUPANCY_MODE_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

UPDATE_ATTRIBUTES_LOAD_CONTROLLER = [
    ATTR_POWER_MODE,
    ATTR_INTENSITY,
    ATTR_RSSI,
    ATTR_WATTAGE,
    ATTR_WATTAGE_INSTANT,
    ATTR_OCCUPANCY_MODE
]

UPDATE_ATTRIBUTES_VALVE = [
    ATTR_MOTOR_POSITION,
    ATTR_MOTOR_TARGET_POSITION
]
# motorPosition,motorTargetPosition,temperatureAlarmStatus,batteryStatus,valveClosureSource,batteryVoltage

UPDATE_ATTRIBUTES_OUTLET = [
    ATTR_ONOFF,
    ATTR_WATTAGE_INSTANT
]

IMPLEMENTED_LOAD_CONTROLLER_TYPES = [120] #power control device
IMPLEMENTED_VALVE_SKU = ["VA4200WZ", "VA4201WZ"]
IMPLEMENTED_OUTLET_SKU = ["SP2600ZB", "SP2610ZB"]
IMPLEMENTED_CALYPSO_SKU = ["RM3500ZB"]

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up neviweb switch."""
    _LOGGER.debug("Entering switch setup_entry")
    data = hass.data[DOMAIN]
    entities = []
    for device in data.devices:
        if device.type in IMPLEMENTED_LOAD_CONTROLLER_TYPES:
            entities.append(NeviwebSwitchLoadController(data.neviweb_client, device))
        elif device.sku in IMPLEMENTED_VALVE_SKU:
            entities.append(NeviwebSwitchValve(data.neviweb_client, device))
        elif device.sku in IMPLEMENTED_OUTLET_SKU or \
            device.sku in IMPLEMENTED_CALYPSO_SKU:
            entities.append(NeviwebSwitchOutlet(data.neviweb_client, device))

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

class NeviwebSwitchBase(SwitchEntity):
    """Implementation of a Neviweb switch."""

    def __init__(self, client: NeviwebClient, device: NeviwebDeviceInfo):
        """Initialize."""
        self._device = device
        self._client = client

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
        device_info = {
            "identifiers": {
                (DOMAIN, self.unique_id),
                (DOMAIN, self._device.identifier)
            },
            "name": self._device.name,
            "manufacturer": self._device.vendor,
            "model": self._device.sku,
            "sw_version": self._device.software_version,
            "suggested_area": self._device.group.name,
            "configuration_url": self._device.configuration_url
        }
        if self._device.via_device_id:
            device_info["via_device_id"] = self._device.via_device_id
        return device_info

    async def async_set_operation_mode(self, operation_mode):
        _LOGGER.debug("async_set_operation_mode %s for %s ", operation_mode,
            self._device.name)
        await self._client.async_set_operation_mode(self.unique_id, operation_mode)

    async def async_set_occupancy_mode(self, occupancy_mode):
        _LOGGER.debug("async_set_occupancy_mode %s for %s ", occupancy_mode,
            self._device.name)
        await self._client.async_set_occupancy_mode(self.unique_id, occupancy_mode)

class NeviwebSwitchLoadController(NeviwebSwitchBase):
    """Implementation of a Neviweb load controller."""

    def __init__(self, client: NeviwebClient, device: NeviwebDeviceInfo):
        """Initialize."""
        super().__init__(client, device)
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
            self.unique_id, UPDATE_ATTRIBUTES_LOAD_CONTROLLER)
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {'operation_mode': self.operation_mode,
                'rssi': self._rssi,
                'occupancy': self._occupancy,
                'wattage': self._wattage,
                'current_power_w': self._current_power_w,
                'today_energy_kwh': self._today_energy_kwh}

    @property
    def operation_mode(self):
        return self._operation_mode

    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._current_power_w == 0

class NeviwebSwitchValve(NeviwebSwitchBase):
    """Implementation of a Neviweb water valve switch."""
    def __init__(self, client: NeviwebClient, device: NeviwebDeviceInfo):
        """Initialize."""
        super().__init__(client, device)
        self._motor_position = 0
        self._motor_target_position = 0
        _LOGGER.debug("Setting up valve %s", self._device.name)

    async def async_update(self):
        """Get the latest data from Neviweb and update the state."""
        start = time.time()
        device_data = await self._client.async_get_device_attributes(
            self.unique_id, UPDATE_ATTRIBUTES_VALVE)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._device.name, elapsed, device_data)
        if "error" not in device_data:
            if "errorCode" not in device_data:
                self._motor_position = device_data[ATTR_MOTOR_POSITION] if \
                    device_data[ATTR_MOTOR_POSITION] is not None else 0.0
                self._motor_target_position = device_data[ATTR_MOTOR_TARGET_POSITION] if \
                    device_data[ATTR_MOTOR_TARGET_POSITION] is not None else 0.0
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
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._motor_position != 0

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.async_set_motor_position(self.unique_id, 100)
        await asyncio.sleep(7)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.async_set_motor_position(self.unique_id, 0)
        await asyncio.sleep(7)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {'motor_target_position': self._motor_target_position}


class NeviwebSwitchOutlet(NeviwebSwitchBase):
    """Implementation of a Neviweb outlet switch."""
    def __init__(self, client: NeviwebClient, device: NeviwebDeviceInfo):
        """Initialize."""
        super().__init__(client, device)
        self._on_off = ""
        self._wattage_instant = 0
        _LOGGER.debug("Setting up outlet %s", self._device.name)

    async def async_update(self):
        """Get the latest data from Neviweb and update the state."""
        start = time.time()
        device_data = await self._client.async_get_device_attributes(
            self.unique_id, UPDATE_ATTRIBUTES_OUTLET)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._device.name, elapsed, device_data)
        if "error" not in device_data:
            if "errorCode" not in device_data:
                self._on_off = device_data[ATTR_ONOFF] if \
                    device_data[ATTR_ONOFF] is not None else ""
                self._wattage_instant = device_data[ATTR_WATTAGE_INSTANT] if \
                    device_data[ATTR_WATTAGE_INSTANT] is not None else 0
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
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._on_off == STATE_ON

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.async_set_on_off(self.unique_id, STATE_ON)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.async_set_on_off(self.unique_id, STATE_OFF)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._wattage_instant

    @property
    def device_class(self):
        """Return the class of this device"""
        if self._device.sku in IMPLEMENTED_CALYPSO_SKU:
            return SwitchDeviceClass.SWITCH
        return SwitchDeviceClass.OUTLET