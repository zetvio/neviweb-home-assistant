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
from . import (SCAN_INTERVAL)
from homeassistant.components.switch import (SwitchDevice, 
    ATTR_TODAY_ENERGY_KWH, ATTR_CURRENT_POWER_W)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'neviweb switch'

STATE_AUTO = 'auto'
STATE_MANUAL = 'manual'
STATE_AWAY = 'away'
STATE_STANDBY = 'bypass'
NEVIWEB_TO_HA_STATE = {
    1: STATE_MANUAL,
    2: STATE_AUTO,
    3: STATE_AWAY,
    130: STATE_STANDBY
}

IMPLEMENTED_DEVICE_TYPES = [120] #power control device

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Neviweb switch."""
    data = hass.data[neviweb.DATA_DOMAIN]
    
    devices = []
    for device_info in data.neviweb_client.gateway_data:
        if device_info["type"] in IMPLEMENTED_DEVICE_TYPES:
            device_name = '{} {}'.format(DEFAULT_NAME, device_info["name"])
            devices.append(NeviwebSwitch(data, device_info, device_name))

    add_devices(devices, True)
    
def keyCheck(key, arr, default, name):
    if key in arr.keys():
        return arr[key]
    else:
        _LOGGER.debug("Neviweb missing %s for %s", key, name)
        return default   

class NeviwebSwitch(SwitchDevice):
    """Implementation of a Neviweb switch."""

    def __init__(self, data, device_info, name):
        """Initialize."""
        self._name = name
        self._client = data.neviweb_client
        self._id = device_info["id"]
        self._wattage = keyCheck("wattage", device_info, 0, name)
        self._brightness = None
        self._operation_mode = None
        self._alarm = None
        self._current_power_w = None
        self._today_energy_kwh = None
        self._rssi = None
        _LOGGER.debug("Setting up %s: %s", self._name, device_info)

    def update(self):
        """Get the latest data from Neviweb and update the state."""
        start = time.time()
        device_data = self._client.get_device_data(self._id)
        device_daily_stats = self._client.get_device_daily_stats(self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)
        if "errorCode" not in device_data:
            self._brightness = device_data["intensity"] if \
                device_data["intensity"] is not None else 0.0
            self._operation_mode = device_data["mode"] if \
                device_data["mode"] is not None else 1
            self._alarm = device_data["alarm"]
            self._current_power_w = device_data["powerWatt"]
            self._rssi = device_data["rssi"]
            self._today_energy_kwh = device_daily_stats[0] / 1000
            return
        _LOGGER.warning("Cannot update %s: %s", self._name, device_data)     

    @property
    def unique_id(self):
        """Return unique ID based on Neviweb device ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property  
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._brightness != 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._client.set_brightness(self._id, 100)
        
    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._client.set_brightness(self._id, 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'alarm': self._alarm,
                'operation_mode': self.operation_mode,
                'rssi': self._rssi,
                'wattage': self._wattage,
                'id': self._id}
       
    @property
    def operation_mode(self):
        return self.to_hass_operation_mode(self._operation_mode)

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

    def to_hass_operation_mode(self, mode):
        """Translate neviweb operation modes to hass operation modes."""
        if mode in NEVIWEB_TO_HA_STATE:
            return NEVIWEB_TO_HA_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to hass", mode)
        return None
