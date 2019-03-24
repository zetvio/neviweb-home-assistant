import logging
import requests
import json
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_API_KEY, CONF_ID,
    CONF_SCAN_INTERVAL, CONF_TIME_ZONE, CONF_LONGITUDE, CONF_LATITUDE)
from homeassistant.util import Throttle

#REQUIREMENTS = ['PY_Sinope==0.1.0']

DOMAIN = 'sinope'
DATA_DOMAIN = 'data_' + DOMAIN
CONF_SERVER = 'server'
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=900)

REQUESTS_TIMEOUT = 30

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_SERVER): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, hass_config):
    """Set up sinope."""
#    import pysinope
    data = SinopeData(hass_config[DOMAIN])
    hass.data[DATA_DOMAIN] = data

    global SCAN_INTERVAL 
    SCAN_INTERVAL = hass_config[DOMAIN].get(CONF_SCAN_INTERVAL)
    _LOGGER.debug("Setting scan interval to: %s", SCAN_INTERVAL)
    
    discovery.load_platform(hass, 'climate', DOMAIN, {}, hass_config)
    discovery.load_platform(hass, 'light', DOMAIN, {}, hass_config)
    discovery.load_platform(hass, 'switch', DOMAIN, {}, hass_config)

    return True

class SinopeData:
    """Get the latest data and update the states."""

    def __init__(self, config):
        """Init the sinope data object."""
        api_key = config.get(CONF_API_KEY)
        api_id = config.get(CONF_ID)
        server = config.get(CONF_SERVER)
        city_name = "Montreal" # FIXME must come from configuration.yaml
        tz = config.get(CONF_TIME_ZONE)
        latitude = config.get(CONF_LATITUDE)
        longitude = config.get(CONF_LONGITUDE)
        self.sinope_client = SinopeClient(api_key, api_id, server, city_name, tz, latitude, longitude)

    # Need some refactoring here concerning the class used to transport data
    # @Throttle(SCAN_INTERVAL)
    # def update(self):
    #     """Get the latest data from pysinope."""
    #     self.sinope_client.update()
    #     _LOGGER.debug("Sinope data updated successfully")



# According to HA: 
# https://developers.home-assistant.io/docs/en/creating_component_code_review.html
# "All API specific code has to be part of a third party library hosted on PyPi. 
# Home Assistant should only interact with objects and not make direct calls to the API."
# So all code below this line should eventually be integrated in a PyPi project.

#from PY_Sinope import pysinope

class PySinopeError(Exception):
    pass

class SinopeClient(object):

    def __init__(self, api_key, api_id, server, city_name, tz, latitude, longitude, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self._api_key = api_key
        self._api_id = api_id
        self._network_name = server
        self._city_name = city_name
        self._tz = tz
        self._latitude = latitude
        self._longitude = longitude
        self.device_data = {}

    def get_climate_device_data(self, device_id):
        """Get device data."""
        # Prepare return
        data = {}
        # send requests
        try:
            temperature = get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_temperature))).hex())
            setpoint = get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_setpoint))).hex())
            heatlevel = get_heat_level(bytearray(send_request(data_read_request(data_read_command,device_id,data_heat_level))).hex())
            mode = get_mode(bytearray(send_request(data_read_request(data_read_command,device_id,data_mode))).hex())
            away = get_is_away(bytearray(send_request(data_read_request(data_read_command,device_id,data_away))).hex())
        except OSError:
            raise PySinopeError("Cannot get climate data")
        # Prepare data
        data = "{'setpoint': '"+setpoint+"', 'mode': "+mode+", 'alarm': 0, 'rssi': 0, 'temperature': "+temperature+", 'heatLevel': "+heatlevel+", 'away': "+away+"}"
        return data

    def get_light_device_data(self, device_id):
        """Get device data."""
        # Prepare return
        data = {}
        # send requests
        try:
            intensity = get_intensity(bytearray(send_request(data_read_request(data_read_command,device_id,data_light_intensity))).hex())
            mode = get_mode(bytearray(send_request(data_read_request(data_read_command,device_id,data_light_mode))).hex())
        except OSError:
            raise PySinopeError("Cannot get light data")
        # Prepare data
        data = "{'intensity': '"+intensity+"', 'mode': "+mode+", 'alarm': 0, 'rssi': 0}"
        return data

    def get_switch_device_data(self, device_id):
        """Get device data."""
        # Prepare return
        data = {}
        # send requests
        try:
            intensity = get_intensity(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_intensity))).hex())
            mode = get_mode(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_mode))).hex())
            powerwatt = get_power_load(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_connected))).hex())
        except OSError:
            raise PySinopeError("Cannot get switch data")
        # Prepare data
        data = "{'intensity': '"+intensity+"', 'mode': "+mode+", 'powerWatt': "+powerwatt+", 'alarm': 0, 'rssi': 0}"
        return data    
    
    def get_climate_device_info(self, device_id):
        """Get information for this device."""
        # Prepare return
        data = {}
        # send requests
        try:
            tempmax = get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_max_temp))).hex())
            tempmin = get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_min_temp))).hex())
            wattload = get_power_load(bytearray(send_request(data_read_request(data_read_command,device_id,data_load))).hex())
            wattoveride = get_power_load(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_connected))).hex())
        except OSError:
            raise PySinopeError("Cannot get climate info")    
        # Prepare data
        data = "{'active': 1, 'tempMax': "+tempmax+", 'tempMin': "+tempmin+", 'wattage': "+wattload+", 'wattageOverride': "+wattoveride+"}"
        return data

    def get_light_device_info(self, device_id):
        """Get information for this device."""
        # Prepare return
        data = {}
        # send requests
        try:
            timer = get_timer_lenght(bytearray(send_request(data_read_request(data_read_command,device_id,data_light_timer))).hex())        except OSError:
        except OSError:
            raise PySinopeError("Cannot get light info")    
        # Prepare data
        data = "{'active': 1, 'timer': "+timer+"}"
        return data

    def get_switch_device_info(self, device_id):
        """Get information for this device."""
        # Prepare return
        data = {}
        # send requests
        try:
            wattload = get_power_load(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_load))).hex())
            timer = get_timer_lenght(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_timer))).hex())
        except OSError:
            raise PySinopeError("Cannot get switch info")    
        # Prepare data
        data = "{'active': 1, 'wattage': "+wattload+", 'timer': "+timer+"}"
        return data

    def set_brightness(self, device_id, brightness):
        """Set device intensity."""
        try:
            result = get_result(bytearray(send_request(data_write_request(data_write_command,device_id,data_light_intensity,set_intensity(brightness)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device brightness")
        return result

    def set_mode(self, device_id, device_type, mode):
        """Set device operation mode."""
        # prepare data
        try:
            if device_type < 100:
                result = get_result(bytearray(send_request(data_write_request(data_write_command,device_id,data_mode,set_mode(mode)))).hex())
            else:
                result = get_result(bytearray(send_request(data_write_request(data_write_command,device_id,data_light_mode,set_mode(mode)))).hex())
        except OSError:
            raise PyNeviwebError("Cannot set device operation mode")
        return result
      
    def set_is_away(self, device_id, away):
        """Set device away mode."""
        try:
            if device_id == "all":
                device_id = "FFFFFFFF"
                result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_away,set_is_away(away)))).hex())
            else:    
                result = get_result(bytearray(send_request(data_write_request(data_write_command,device_id,data_away,set_is_away(away)))).hex())
        except OSError:
            raise PyNeviwebError("Cannot set device away mode")
        return result 
      
    def set_temperature(self, device_id, temperature):
        """Set device temperature."""
        try:
            result = get_result(bytearray(send_request(data_write_request(data_write_command,device_id,data_setpoint,set_temperature(temperature)))).hex())
        except OSError:
            raise PyNeviwebError("Cannot set device setpoint temperature")
        return result

    def set_timer(self, device_id, timer_length):
        """Set device timer length."""
        try:
            result = get_result(bytearray(send_request(data_write_request(data_write_command,device_id,data_light_timer,set_timer_length(timer_length)))).hex())
        except OSError:
            raise PyNeviwebError("Cannot set device timer length")
        return result 
    
    def set_report(self, device_id):
        """Set report to send data to each devices"""
        try:
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_time,set_time()))).hex())
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_date,set_date()))).hex())
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_sunrise,set_sun_time("sunrise")))).hex())
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_sunset,set_sun_time("sunset")))).hex())
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_outdoor_temperature,set_temperature(get_outside_temperature())))).hex())
        except OSError:
            raise PyNeviwebError("Cannot send report to each devices")
        return result
