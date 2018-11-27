"""
Support for Sinope switch.
type 120 = load controller device, RM3250RF and RM3200RF
For more details about this platform, please refer to the documentation at  https://www.sinopetech.com/en/support/#api
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol
import json
import re

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_NAME)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Sinope switch'

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
      if device["info"]["type"] == 120: #power control devise
        devices.append(SinopeSwitch(sinope_data, id, '{} {}'.format(name, device["info"]["name"])))

    add_devices(devices, True)

class SinopeSwitch(SwitchDevice):
    """Implementation of a Sinope switch Device."""

    def __init__(self, sinope_data, device_id, name):
        """Initialize."""
        self.client_name = name
        self.client = sinope_data.client
        self.device_id = device_id
        self.sinope_data = sinope_data

    def update(self):
        """Get the latest data from Sinope and update the state."""
        self.sinope_data.update()
        self._brightness = int(self.sinope_data.data[self.device_id]["data"]["intensity"])

    @property
    def name(self):
        """Return the name of the sinope, if any."""
        return self.client_name
      
    @property  
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._brightness != 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        brightness = 100
        self.client.set_brightness(self.device_id, brightness)
        
    def turn_off(self, **kwargs):
        """Turn the device off."""
        brightness = self._brightness
        if brightness is None or brightness == 0:
            return
        self.client.set_brightness(self.device_id, 0)
        
    @property
    def mode(self):
        return self._mode

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
            _LOGGER.error("Error on receive last Sinope switch data: %s", exp)
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
      
    def set_brightness(self, device, brightness):
        """Set device intensity."""
        data = {"intensity": brightness}
        try:
            raw_res = requests.put(DEVICE_DATA_URL + str(device) + "/intensity", data=data, headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Cannot set device brightness")
