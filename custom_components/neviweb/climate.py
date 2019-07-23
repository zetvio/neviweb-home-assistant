"""
Support for Neviweb thermostat.
type 10 = thermostat TH1120RF 3000W and 4000W
type 20 = thermostat TH1300RF 3600W floor, TH1500RF double pole thermostat
type 21 = thermostat TH1400RF low voltage
For more details about this platform, please refer to the documentation at  
https://www.sinopetech.com/en/support/#api
"""
import logging

import voluptuous as vol
import time

import custom_components.neviweb as neviweb
from . import (SCAN_INTERVAL)
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (HVAC_MODE_HEAT, 
    HVAC_MODE_OFF, HVAC_MODE_AUTO, SUPPORT_TARGET_TEMPERATURE, 
    SUPPORT_PRESET_MODE, PRESET_AWAY, PRESET_NONE, CURRENT_HVAC_HEAT, 
    CURRENT_HVAC_IDLE, CURRENT_HVAC_OFF)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, 
    ATTR_TEMPERATURE)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)

DEFAULT_NAME = "neviweb climate"

NEVIWEB_MODE_OFF = 0
NEVIWEB_MODE_FREEZE_PROTECT = 1
NEVIWEB_MODE_MANUAL = 2
NEVIWEB_MODE_AUTO = 3
NEVIWEB_MODE_AWAY = 5

NEVIWEB_BYPASS_FLAG = 128
NEVIWEB_BYPASSABLE_MODES = [NEVIWEB_MODE_FREEZE_PROTECT,
                            NEVIWEB_MODE_AUTO,
                            NEVIWEB_MODE_AWAY]
NEVIWEB_MODE_AUTO_BYPASS = (NEVIWEB_MODE_AUTO | NEVIWEB_BYPASS_FLAG)

SUPPORTED_HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

PRESET_BYPASS = 'temporary'
PRESET_MODES = [
    PRESET_NONE,
    PRESET_AWAY,
    PRESET_BYPASS
]

IMPLEMENTED_DEVICE_TYPES = [10, 20, 21]

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the neviweb thermostats."""
    data = hass.data[neviweb.DATA_DOMAIN]
    
    devices = []
    for device_info in data.neviweb_client.gateway_data:
        if device_info["type"] in IMPLEMENTED_DEVICE_TYPES:
            device_name = "{} {}".format(DEFAULT_NAME, device_info["name"])
            devices.append(NeviwebThermostat(data, device_info, device_name))

    add_devices(devices, True)

class NeviwebThermostat(ClimateDevice):
    """Implementation of a Neviweb thermostat."""

    def __init__(self, data, device_info, name):
        """Initialize."""
        self._name = name
        self._client = data.neviweb_client
        self._id = device_info["id"]
        self._wattage = device_info["wattage"]
        self._wattage_override = device_info["wattageOverride"]
        self._min_temp = device_info["tempMin"]
        self._max_temp = device_info["tempMax"]
        self._target_temp = None
        self._cur_temp = None
        self._rssi = None
        self._alarm = None
        self._operation_mode = None
        self._heat_level = 0
        _LOGGER.debug("Setting up %s: %s", self._name, device_info)

    def update(self):
        """Get the latest data from Neviweb and update the state."""
        start = time.time()
        device_data = self._client.get_device_data(self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
        self._name, elapsed, device_data)

        if "errorCode" in device_data:
            if device_data["errorCode"] == None:
                self._cur_temp = float(device_data["temperature"])
                self._target_temp = float(device_data["setpoint"]) if \
                    device_data["setpoint"] is not None else 0.0
                self._heat_level = device_data["heatLevel"] if \
                    device_data["heatLevel"] is not None else 0
                self._alarm = device_data["alarm"]
                self._rssi = device_data["rssi"]
                self._operation_mode = device_data["mode"] if \
                    device_data["mode"] is not None else NEVIWEB_MODE_MANUAL
                return
        elif "code" in device_data:
            _LOGGER.warning("Error while updating %s. %s: %s", self._name,
                device_data["code"], device_data["message"])
        else:
            _LOGGER.warning("Cannot update %s: %s", self._name, device_data)

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
        return {'alarm': self._alarm,
                'heat_level': self._heat_level,
                'rssi': self._rssi,
                'wattage': self._wattage,
                'wattage_override': self._wattage_override,
                'id': self._id}

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
        if self._operation_mode == NEVIWEB_MODE_OFF:
            return HVAC_MODE_OFF
        elif self._operation_mode in [NEVIWEB_MODE_AUTO, 
                                      NEVIWEB_MODE_AUTO_BYPASS]:
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
        if self._operation_mode & NEVIWEB_BYPASS_FLAG == NEVIWEB_BYPASS_FLAG:
            return PRESET_BYPASS
        elif self._operation_mode == NEVIWEB_MODE_AWAY:
            return PRESET_AWAY
        else:
            return PRESET_NONE

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        if self._operation_mode == NEVIWEB_MODE_OFF:
            return CURRENT_HVAC_OFF
        elif self._heat_level == 0:
            return CURRENT_HVAC_IDLE
        else:
            return CURRENT_HVAC_HEAT

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._client.set_temperature(self._id, temperature)
        self._target_temp = temperature

    def set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._client.set_mode(self._id, NEVIWEB_MODE_OFF)
        elif hvac_mode == HVAC_MODE_HEAT:
            self._client.set_mode(self._id, NEVIWEB_MODE_MANUAL)
        elif hvac_mode == HVAC_MODE_AUTO:
            self._client.set_mode(self._id, NEVIWEB_MODE_AUTO)
        else:
            _LOGGER.error("Unable to set hvac mode: %s.", hvac_mode)

    def set_preset_mode(self, preset_mode):
        """Activate a preset."""
        if preset_mode == self.preset_mode:
            return

        if preset_mode == PRESET_AWAY:
            self._client.set_mode(self._id, NEVIWEB_MODE_AWAY)
        elif preset_mode == PRESET_BYPASS:
            if self._operation_mode in NEVIWEB_BYPASSABLE_MODES:
                self._client.set_mode(self._id, self._operation_mode | 
                NEVIWEB_BYPASS_FLAG)
        elif preset_mode == PRESET_NONE:
            # Re-apply current hvac_mode without any preset
            self.set_hvac_mode(self.hvac_mode)
        else:
            _LOGGER.error("Unable to set preset mode: %s.", preset_mode)
