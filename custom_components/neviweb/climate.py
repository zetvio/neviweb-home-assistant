"""
Support for Neviweb thermostat.
type 10 = thermostat TH1120RF 3000W and 4000W,
type 10 = thermostat TH1121RF 3000W and 4000W, (Public place)
type 20 = thermostat TH1300RF 3600W floor, 
type 20 = thermostat TH1500RF double pole thermostat,
type 21 = thermostat TH1400RF low voltage,
type 21 = thermostat TH1400WF low voltage, (wifi)
For more details about this platform, please refer to the documentation at  
https://www.sinopetech.com/en/support/#api
"""
import logging

import voluptuous as vol
import time

import custom_components.neviweb as neviweb
from . import (SCAN_INTERVAL)
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (HVAC_MODE_HEAT, 
    HVAC_MODE_OFF, HVAC_MODE_AUTO, SUPPORT_TARGET_TEMPERATURE, 
    SUPPORT_PRESET_MODE, PRESET_AWAY, PRESET_NONE, CURRENT_HVAC_HEAT, 
    CURRENT_HVAC_IDLE, CURRENT_HVAC_OFF, ATTR_HVAC_MODE)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, 
    ATTR_TEMPERATURE)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval
from .const import (DOMAIN, ATTR_RSSI, ATTR_SETPOINT_MODE, ATTR_ROOM_SETPOINT,
    ATTR_OUTPUT_PERCENT_DISPLAY, ATTR_ROOM_TEMPERATURE, ATTR_ROOM_SETPOINT_MIN,
    ATTR_ROOM_SETPOINT_MAX, ATTR_WATTAGE, MODE_AUTO, MODE_AUTO_BYPASS, 
    MODE_MANUAL, MODE_OFF, MODE_AWAY)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)

DEFAULT_NAME = "neviweb climate"
PARALLEL_UPDATES = 1

UPDATE_ATTRIBUTES = [ATTR_SETPOINT_MODE, ATTR_RSSI, ATTR_ROOM_SETPOINT,
    ATTR_OUTPUT_PERCENT_DISPLAY, ATTR_ROOM_TEMPERATURE, ATTR_ROOM_SETPOINT_MIN,
    ATTR_ROOM_SETPOINT_MAX]

SUPPORTED_HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

PRESET_BYPASS = 'temporary'
PRESET_MODES = [
    PRESET_NONE,
    PRESET_AWAY,
    PRESET_BYPASS
]

IMPLEMENTED_LOW_VOLTAGE = [21]
IMPLEMENTED_THERMOSTAT = [10, 20]
IMPLEMENTED_DEVICE_TYPES = IMPLEMENTED_THERMOSTAT + IMPLEMENTED_LOW_VOLTAGE

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the neviweb thermostats."""
    data = hass.data[DOMAIN]
    
    # _LOGGER.debug("Entering climate setup with data: %s", data)
    devices = []
    for device_info in data.devices:
        if "signature" in device_info and \
            "type" in device_info["signature"] and \
            device_info["signature"]["type"] in IMPLEMENTED_DEVICE_TYPES:
            device_name = "{} {}".format(DEFAULT_NAME, device_info["name"])
            devices.append(NeviwebThermostat(data, device_info, device_name))
            
    async_add_entities(devices, True)

class NeviwebThermostat(ClimateEntity):
    """Implementation of a Neviweb thermostat."""

    def __init__(self, data, device_info, name):
        """Initialize."""
        self._name = name
        self._client = data.neviweb_client
        self._id = device_info["id"]
        self._wattage = 0
        #self._wattage_override = device_info["wattageOverride"]
        self._min_temp = 0
        self._max_temp = 0
        self._target_temp = None
        self._cur_temp = None
        self._rssi = None
        #self._alarm = None
        self._operation_mode = None
        self._heat_level = 0
        self._is_low_voltage = device_info["signature"]["type"] in \
            IMPLEMENTED_LOW_VOLTAGE
        _LOGGER.debug("Setting up %s: %s", self._name, device_info)

    async def async_update(self):
        """Get the latest data from Neviweb and update the state."""
        if not self._is_low_voltage:
            WATT_ATTRIBUTE = [ATTR_WATTAGE]
        else:
            WATT_ATTRIBUTE = []
        start = time.time()
        device_data = await self._client.async_get_device_attributes(self._id,
            UPDATE_ATTRIBUTES + WATT_ATTRIBUTE)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)

        if "error" not in device_data:
            if "errorCode" not in device_data:
                self._cur_temp = float(device_data[ATTR_ROOM_TEMPERATURE]["value"])
                self._target_temp = float(device_data[ATTR_ROOM_SETPOINT]) if \
                    device_data[ATTR_SETPOINT_MODE] != MODE_OFF else 0.0
                self._heat_level = device_data[ATTR_OUTPUT_PERCENT_DISPLAY]
                #self._alarm = device_data["alarm"]
                self._rssi = device_data[ATTR_RSSI]
                self._operation_mode = device_data[ATTR_SETPOINT_MODE]
                self._min_temp = device_data[ATTR_ROOM_SETPOINT_MIN]
                self._max_temp = device_data[ATTR_ROOM_SETPOINT_MAX]
                if not self._is_low_voltage:
                    self._wattage = device_data[ATTR_WATTAGE]["value"]
                return
            else:
                if device_data["errorCode"] == "ReadTimeout":
                    _LOGGER.warning("Error in reading device %s: (%s), too slow to respond or busy.", self._name, device_data)
                else:
                    _LOGGER.warning("Unknown errorCode, device: %s, error: %s", self._name, device_data)
            return
        else:
            if device_data["error"]["code"] == "DVCCOMMTO":  
                _LOGGER.warning("Cannot update %s: %s. Device is busy or does not respond quickly enough.", self._name, device_data)
            elif device_data["error"]["code"] == "SVCINVREQ":
                _LOGGER.warning("Invalid or malformed request to Neviweb, %s:",  device_data)
            elif device_data["error"]["code"] == "DVCUNVLB":
                _LOGGER.warning("Device %s unavailable, Neviweb maintnance update, %s:", self._name, device_data)
            elif device_data["error"]["code"] == "SVCERR":
                _LOGGER.warning("Device %s statistics unavailables, %s:", self._name, device_data)
            else:
                _LOGGER.warning("Unknown error, device: %s, error: %s", self._name, device_data)

    @property
    def unique_id(self):
        """Return unique ID based on Neviweb device ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = {}
        if not self._is_low_voltage:
            data = {'wattage': self._wattage}
        data.update ({'heat_level': self._heat_level,
                      'rssi': self._rssi,
                      'id': self._id})
        return data

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the min temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the max temperature."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation"""
        if self._operation_mode == MODE_OFF:
            return HVAC_MODE_OFF
        elif self._operation_mode in [MODE_AUTO, MODE_AUTO_BYPASS]:
            return HVAC_MODE_AUTO
        else:
            return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return SUPPORTED_HVAC_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp
    
    @property
    def target_temperature (self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return PRESET_MODES

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._operation_mode in [MODE_AUTO_BYPASS]:
            return PRESET_BYPASS
        elif self._operation_mode == MODE_AWAY:
            return PRESET_AWAY
        else:
            return PRESET_NONE

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        if self._operation_mode == MODE_OFF:
            return CURRENT_HVAC_OFF
        elif self._heat_level == 0:
            return CURRENT_HVAC_IDLE
        else:
            return CURRENT_HVAC_HEAT

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        temperature = kwargs.get(ATTR_TEMPERATURE)
        
        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if temperature is not None:
            await self._client.async_set_temperature(self._id, temperature)
        

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._client.async_set_setpoint_mode(self._id, MODE_OFF)
        elif hvac_mode == HVAC_MODE_HEAT:
            await self._client.async_set_setpoint_mode(self._id, MODE_MANUAL)
        elif hvac_mode == HVAC_MODE_AUTO:
            await self._client.async_set_setpoint_mode(self._id, MODE_AUTO)
        else:
            _LOGGER.error("Unable to set hvac mode: %s.", hvac_mode)

    async def async_set_preset_mode(self, preset_mode):
        """Activate a preset."""
        if preset_mode == self.preset_mode:
            return

        if preset_mode == PRESET_AWAY:
            await self._client.async_set_setpoint_mode(self._id, MODE_AWAY)
        elif preset_mode == PRESET_BYPASS:
            if self._operation_mode == MODE_AUTO:
                await self._client.async_set_setpoint_mode(self._id, MODE_AUTO_BYPASS)
        elif preset_mode == PRESET_NONE:
            # Re-apply current hvac_mode without any preset
            await self.async_set_hvac_mode(self.hvac_mode)
        else:
            _LOGGER.error("Unable to set preset mode: %s.", preset_mode)
