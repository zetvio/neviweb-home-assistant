"""
Support for Sinope thermostat.
type 10 = thermostat TH1120RF 3000W and 4000W
type 20 = thermostat TH1300RF 3600W floor, TH1500RF double pole thermostat
type 21 = thermostat TH1400RF low voltage
For more details about this platform, please refer to the documentation at  https://www.sinopetech.com/en/support/#api
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol
import json
import re

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA, STATE_HEAT, STATE_IDLE, ATTR_TEMPERATURE, ATTR_AWAY_MODE, ATTR_OPERATION_MODE, ATTR_HOLD_MODE, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, STATE_AUTO, STATE_MANUAL)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_NAME, TEMP_CELSIUS, STATE_OFF)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_OPERATION_MODE)

DEFAULT_NAME = 'Sinope'

REQUESTS_TIMEOUT = 30
SCAN_INTERVAL = timedelta(seconds=900)

HOST = "https://neviweb.com"
LOGIN_URL = "{}/api/login".format(HOST)
GATEWAY_URL = "{}/api/gateway".format(HOST)
GATEWAY_DEVICE_URL = "{}/api/device?gatewayId=".format(HOST)
DEVICE_DATA_URL = "{}/api/device/".format(HOST)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sinope sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    gateway = config.get("gateway")

    try:
        sinope_data = SinopeData(username, password, gateway)
        sinope_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Fail to login: %s", error)
        return False

    name = config.get(CONF_NAME)

    devices = []
    for id, device in sinope_data.data.items():
        if device["info"]["type"] == 10 or device["info"]["type"] == 20 or device["info"]["type"] == 21:
            devices.append(SinopeThermostat(sinope_data, id, '{} {}'.format(name, device["info"]["name"])))

    add_devices(devices, True)

class SinopeThermostat(ClimateDevice):
    """Implementation of a Sinope Device."""

    def __init__(self, sinope_data, device_id, name):
        """Initialize."""
        self.client_name = name
        self.client = sinope_data.client
        self.device_id = device_id
        self.sinope_data = sinope_data
        self._target_temp  = None
        self._cur_temp = None
        self._min_temp  = float(self.sinope_data.data[self.device_id]["info"]["tempMin"])
        self._max_temp  = float(self.sinope_data.data[self.device_id]["info"]["tempMax"])
        self._mode = None
        self._alarm = None
        self._operation_mode = None
        self._operation_list = [STATE_OFF, STATE_MANUAL, STATE_AUTO]
        self._state = None
        self._away = False

    def update(self):
        """Get the latest data from Sinope and update the state."""
        self.sinope_data.update()
        self._target_temp  = float(self.sinope_data.data[self.device_id]["data"]["setpoint"])
        self._cur_temp =  float(self.sinope_data.data[self.device_id]["data"]["temperature"])
        self._operation_mode = int(self.sinope_data.data[self.device_id]["data"]["mode"])
        self._state = int(self.sinope_data.data[self.device_id]["data"]["heatLevel"])
        self._alarm = int(self.sinope_data.data[self.device_id]["data"]["alarm"])
        
    def hass_operation_to_sinope(self, mode):
        """Translate hass operation modes to sinope modes."""
        if mode == STATE_OFF:
            return 0
        if mode == STATE_MANUAL:
            return 2
        if mode == STATE_AUTO:
            return 3
        _LOGGER.warning("Sinope have no setting for %s operation", mode)
        
    def sinope_operation_to_hass(self, mode):
        """Translate sinope operation modes to hass operation modes."""
        if self._operation_mode == 0:
            return STATE_OFF
        if self._operation_mode == 2:
            return STATE_MANUAL
        if self._operation_mode == 3:
            return STATE_AUTO 
        _LOGGER.warning("Operation mode %s could not be mapped to hass", self._operation_mode)
        return None       

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the sinope, if any."""
        return self.client_name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
    
    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list
    
    @property
    def target_temperature (self):
        """Return the temperature we try to reach."""
        return self._target_temp

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self.client.set_temperature_device(self.device_id, temperature)
        self._target_temp = temperature
        
     def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        mode = self.hass_operation_to_sinope(operation_mode)
        self.client.set_operation_mode(self.device_id, mode)
        self._operation_mode = mode    

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp

    @property
    def min_temp(self):
        """Return the min temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the max temperature."""
        return self._max_temp
    
    @property
    def state(self):
        """Return current state i.e. heat, idle."""
        if self._state:
            return STATE_HEAT
        return STATE_IDLE

    @property
    def current_operation(self):
        """Return current operation i.e. heat, cool, idle."""
        if self._operation_mode is not None:
            op_mode = self.sinope_operation_to_hass(self._operation_mode)
            return op_mode

    def mode(self):
        return self._mode
    
    def away(self):
        if self._operation_mode == 5:
            return self._away

    def alarm(self):
        return self._alarm

class SinopeData(object):

    def __init__(self, username, password, gateway):
        """Initialize the data object."""
        self.client = SinopeClient(username, password, gateway, REQUESTS_TIMEOUT)
        self.data = {}

    def update(self):
        """Get the latest data from Sinope."""
        try:
            self.client.fetch_data()
        except PySinopeError as exp:
            _LOGGER.error("Error on receive last Sinope data: %s", exp)
            return
        self.data = self.client.get_data()

class PySinopeError(Exception):
    pass


class SinopeClient(object):

    def __init__(self, username, password, gateway, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self.username = username
        self.password = password
        self._headers = None
        self.gateway = gateway
        self.gateway_id = None
        self._data = {}
        self._gateway_data = {}
        self._cookies = None
        self._timeout = timeout
        self._post_login_page()
        self._get_data_gateway()

    def _post_login_page(self):
        """Login to Sinope website."""
        data = {"email": self.username, "password": self.password, "stayConnected": 1}
        try:
            raw_res = requests.post(LOGIN_URL, data=data, cookies=self._cookies, allow_redirects=False, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Can not submit login form")
        if raw_res.status_code != 200:
            raise PySinopeError("Cannot log in")

        # Update session
        self._cookies = raw_res.cookies
        self._headers = {"Session-Id": raw_res.json()["session"]}
        return True

    def _get_data_gateway(self):
        """Get gateway data."""
        # Prepare return
        data = {}
        # Http request
        try:
            raw_res = requests.get(GATEWAY_URL, headers=self._headers, cookies=self._cookies, timeout=self._timeout)
            gateways = raw_res.json()

            for gateway in gateways:
                if gateway["name"] == self.gateway:
                    self.gateway_id = gateway["id"]
                    break
            raw_res = requests.get(GATEWAY_DEVICE_URL + str(self.gateway_id), headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Can not get page data_gateway")
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        self._gateway_data = raw_res.json()

    def _get_data_device(self, device):
        """Get device data."""
        # Prepare return
        data = {}
        # Http request
        try:
            raw_res = requests.get(DEVICE_DATA_URL + str(device) + "/data", headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Can not get page data_device")
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        data = raw_res.json()
        return data

    def fetch_data(self):
        sinope_data = {}
        # Get data each device
        for device in self._gateway_data:
            sinope_data.update({ device["id"] : { "info" : device, "data" : self._get_data_device(device["id"]) }})
        self._data = sinope_data

    def get_data(self):
        """Return collected data"""
        return self._data

    def set_temperature_device(self, device, temperature):
        """Set device temperature."""
        data = {"temperature": temperature}
        try:
            raw_res = requests.put(DEVICE_DATA_URL + str(device) + "/setpoint", data=data, headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Cannot set device temperature")
            
    def set_operation_mode(self, device, mode):
        """Set device operation mode."""
        data = {"mode": mode}
        try:
            raw_res = requests.put(DEVICE_DATA_URL + str(device) + "/mode", data=data, headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Cannot set device operation mode")	  
    
