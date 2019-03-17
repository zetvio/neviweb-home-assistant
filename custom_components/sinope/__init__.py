import logging
import requests
import json
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
    CONF_SCAN_INTERVAL)
from homeassistant.util import Throttle

REQUIREMENTS = ['pysinope==1.0.0']

DOMAIN = 'sinope'
DATA_DOMAIN = 'data_' + DOMAIN
CONF_SERVER = 'server'
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=900)

REQUESTS_TIMEOUT = 30
#HOST = "https://neviweb.com"
#LOGIN_URL = "{}/api/login".format(HOST)
#GATEWAY_URL = "{}/api/gateway".format(HOST)
#GATEWAY_DEVICE_URL = "{}/api/device?gatewayId=".format(HOST)
#DEVICE_DATA_URL = "{}/api/device/".format(HOST)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_API_ID): cv.string,
        vol.Optional(CONF_SERVER): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, hass_config):
    """Set up sinope."""
    import pysinope
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
        # from pysinope import SinopeClient
        api_key = config.get(CONF_API_KEY)
        api_id = config.get(CONF_API_ID)
        server = config.get(CONF_SERVER)
        self.sinope_client = SinopeClient(api_key, api_id, server)

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

class PySinopeError(Exception):
    pass

class SinopeClient(object):

    def __init__(self, api_key, api_id, server, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self._api_key = api_key
        self._api_id = api_id
        self._network_name = server
        self.device_data = {}
        self.__get_device_data()

    def update(self):
        self.__get_device_data()

    def get_device_data(self, device_id):
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
            raise PySinopeError("Cannot get data")
        # Prepare data
        data = "{'setpoint': '"+setpoint+"', 'mode': "+mode+", 'alarm': 0, 'temperature': "+temperature+", 'heatLevel': "+heatlevel+", 'away': "+away+"}"
        return data

    def get_device_info(self, device_id):
        """Get information for this device."""
        # Prepare return
        data = {}
        # send requests
        try:
            tempmax = get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_max_temp))).hex())
            tempmin = get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_min_temp))).hex())
            wattload = get_power_connected(bytearray(send_request(data_read_request(data_read_command,device_id,data_load))).hex())
            wattoveride = get_power_load(bytearray(send_request(data_read_request(data_read_command,device_id,data_power_load))).hex())
        except OSError:
            raise PySinopeError("Cannot get info")    
        # Prepare data
        data = "{'active': 1, 'tempMax': "+tempmax+", 'tempMin': "+tempmin+", 'wattage': "+wattload+", 'wattageOverride': "+wattoveride+"}"
        return data

    def ping_device(self, device_id):
        """Ping a device."""
        # Prepare return
        data = {}
        # Http request
        try:
            raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
                "/ping?force=1", headers=self._headers, cookies=self._cookies,
                timeout=self._timeout)
        except OSError:
            raise PyNeviwebError("Cannot ping device")
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        data = raw_res.json()
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
      
    def set_report(self, device_id):
        """Set report to send data to each devices"""
        try:
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_time,set_time()))).hex()))
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_date,set_date()))).hex()))
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_sunrise,set_sun_time("sunrise")))).hex()))
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_sunset,set_sun_time("sunset")))).hex()))
            if result == False:
                return result
            result = get_result(bytearray(send_request(data_report_request(data_report_command,device_id,data_outdoor_temperature,set_temperature(get_outside_temperature())))).hex()))
        except OSError:
            raise PyNeviwebError("Cannot send report to each devices")
        return result
