"""
Support for Sinope light.
type 102 = light switch SW2500RF
type 112 = light dimmer DM2500RF
For more details about this platform, please refer to the documentation at  https://www.sinopetech.com/en/support/#api
"""
import logging

import requests
import voluptuous as vol
import json
import re

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (Light, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_NAME)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_BRIGHTNESS)

DEFAULT_NAME = 'Sinope dimmer'

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

def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((byt*100.0)/255.0)

def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return (percent*255.0)/100.0

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sinope sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    gateway = config.get("gateway")

    try:
        sinope_data = SinopeData(username, password, gateway)
        sinope_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Failt login: %s", error)
        return False

    name = config.get(CONF_NAME)
    
    devices = []
    for id, device in sinope_data.data.items():
        if device["info"]["type"] == 112:
            devices.append(SinopeDimmer(sinope_data, id, '{} {}'.format(name, device["info"]["name"])))

    add_devices(devices, True)

class SinopeDimmer(Light):
    """Implementation of a Sinope Device."""

    def __init__(self, sinope_data, device_id, name):
        """Initialize."""
        self.client_name = name
        self.client = sinope_data.client
        self.device_id = device_id
        self.sinope_data = sinope_data
        self._id = int(self.sinope_data.data[self.device_id]["info"]["id"])
        self._alarm = None
        self._mode = None
        self._brightness = 255
        self._operation_list = ['Manual', 'Auto', 'Away', 'Hold']
        
    def update(self):
        """Get the latest data from Sinope and update the state."""
        self.sinope_data.update()
        self._brightness  = brightness_from_percentage(int(self.sinope_data.data[self.device_id]["data"]["intensity"]))
        self._alarm = int(self.sinope_data.data[self.device_id]["data"]["alarm"])
        self._mode = int(self.sinope_data.data[self.device_id]["data"]["mode"])

    def hass_operation_to_sinope(self, mode):
        """Translate hass operation modes to sinope modes."""

        if mode == 'Manual':
            return 1
        if mode == 'Auto':
            return 2
        if mode == 'Away':
            return 3
        if mode == 'Hold':
            return 130
        _LOGGER.warning("Sinope have no setting for %s mode", mode)
        return None
        
    def sinope_operation_to_hass(self, mode):
        """Translate sinope operation modes to hass operation modes."""
        if mode == 1:
            return 'Manual'
        if mode == 2:
            return 'Auto'
        if mode == 3:
            return 'Away'
        if mode == 130:
            return 'Hold'  
        _LOGGER.warning("Mode %s could not be mapped to hass", self._operation_mode)
        return None        
        
    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list
    
    @property
    def name(self):
        """Return the name of the sinope, if any."""
        return self.client_name

    @property
    def unique_id(self):
        """Return unique ID based on Sinope ID."""
        return self._id
    
    @property
    def brightness(self):
        return self._brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._brightness != 0

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if kwargs.get(ATTR_BRIGHTNESS):
            brightness = brightness_to_percentage(int(kwargs.get(ATTR_BRIGHTNESS)))
        else:
            """Brightness of 101 sets the light to last known brightness"""
            brightness = 101;
        self.client.set_brightness(self.device_id, brightness)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        brightness = self._brightness
        if brightness is None or brightness == 0:
            return
        self.client.set_brightness(self.device_id, 0)
  
    def set_mode(self, operation_mode):
        """Set new operation mode."""
        mode = self.hass_operation_to_sinope(operation_mode)
        self.client.set_mode(self.device_id, mode)
        self._mode = mode

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'alarm': self._alarm,
                'mode': self._mode}
 
    def mode(self):
        if self._mode is not None:
            op_mode = self.sinope_operation_to_hass(self._mode)
            return op_mode
        """return self._mode"""

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

    def set_brightness(self, device, brightness):
        """Set device brightness."""
        data = {"intensity": brightness}
        try:
            raw_res = requests.put(DEVICE_DATA_URL + str(device) + "/intensity", data=data, headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Cannot set device brightness")

    def set_mode(self, device, mode):
        """Set device operation mode."""
        data = {"mode": mode}
        try:
            raw_res = requests.put(DEVICE_DATA_URL + str(device) + "/mode", data=data, headers=self._headers, cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PySinopeError("Cannot set device operation mode")
