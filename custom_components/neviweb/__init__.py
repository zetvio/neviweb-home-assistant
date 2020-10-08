import logging
import requests
import json
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_USERNAME, CONF_EMAIL, CONF_PASSWORD,
    CONF_SCAN_INTERVAL)
from homeassistant.util import Throttle
from .const import (DOMAIN, CONF_NETWORK, CONF_NETWORK2, ATTR_INTENSITY, ATTR_POWER_MODE,
    ATTR_SETPOINT_MODE, ATTR_ROOM_SETPOINT, ATTR_SIGNATURE)

#REQUIREMENTS = ['PY_Sinope==0.1.5']
VERSION = '1.2.5'


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=540)

REQUESTS_TIMEOUT = 30
HOST = "https://neviweb.com"
LOGIN_URL = "{}/api/login".format(HOST)
LOCATIONS_URL = "{}/api/locations".format(HOST)
GATEWAY_DEVICE_URL = "{}/api/devices?location$id=".format(HOST)
DEVICE_DATA_URL = "{}/api/device/".format(HOST)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NETWORK): cv.string,
        vol.Optional(CONF_NETWORK2): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, hass_config):
    """Set up neviweb."""
    email = hass_config[DOMAIN].get(CONF_USERNAME)
    password = hass_config[DOMAIN].get(CONF_PASSWORD)

    client = NeviwebClient(email, password)
    await client.async_post_login_page()

    locations = await client.async_get_locations()

    data = NeviwebData(client, locations)
    data.devices = []
    await data.async_get_locations_devices()
    hass.data[DOMAIN] = data

    global SCAN_INTERVAL 
    SCAN_INTERVAL = hass_config[DOMAIN].get(CONF_SCAN_INTERVAL)
    _LOGGER.debug("Setting scan interval to: %s", SCAN_INTERVAL)

    hass.async_create_task(
        discovery.async_load_platform(hass, 'climate', DOMAIN, {}, hass_config)
    )
    hass.async_create_task(
        discovery.async_load_platform(hass, 'light', DOMAIN, {}, hass_config)
    )
    hass.async_create_task(
        discovery.async_load_platform(hass, 'switch', DOMAIN, {}, hass_config)
    )
    _LOGGER.debug("Tasks created")

    return True

class NeviwebData:
    """Get the latest data and update the states."""

    def __init__(self, client, locations):
        """Init the neviweb data object."""
        # from pyneviweb import NeviwebClient
        self.neviweb_client = client
        self.locations = locations
        self.devices = None

    async def async_get_locations_devices(self):
        for location in self.locations:
            self.devices += await \
                self.neviweb_client.async_get_location_devices(location.id)


# According to HA: 
# https://developers.home-assistant.io/docs/en/creating_component_code_review.html
# "All API specific code has to be part of a third party library hosted on PyPi. 
# Home Assistant should only interact with objects and not make direct calls to the API."
# So all code below this line should eventually be integrated in a PyPi project.

#from PY_Sinope import pyneviweb

class PyNeviwebError(Exception):
    pass

class NeviwebLocation(object):
    def __init__(self, id, name, mode):
        self.id = id
        self.name = name
        self.mode = mode

class NeviwebClient(object):

    def __init__(self, email, password, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self._email = email
        self._password = password
        self._headers = None
        self._cookies = None
        self._timeout = timeout
        self.user = None      

    # async def async_update(self):
    #     await self.__async_get_gateway_data()

    async def async_post_login_page(self):
        """Login to Neviweb."""
        data = {"username": self._email, "password": self._password, 
            "interface": "neviweb", "stayConnected": 1}
        try:
            raw_res = requests.post(LOGIN_URL, data=data, 
                cookies=self._cookies, allow_redirects=False, 
                timeout=self._timeout)
        except OSError:
            raise PyNeviwebError("Cannot submit login form")
        if raw_res.status_code != 200:
            raise PyNeviwebError("Cannot log in")

        # Update session
        self._cookies = raw_res.cookies
        data = raw_res.json()
        _LOGGER.debug("Login response: %s", data)
        if "error" in data:
            if data["error"]["code"] == "ACCSESSEXC":
                _LOGGER.error("Too many active sessions. Close all Neviweb " +
                "sessions you have opened on other platform (mobile, browser" +
                ", ...), wait a few minutes, then reboot Home Assistant.")
            return False
        else:
            self.user = data["user"]
            self._headers = {"Session-Id": data["session"]}
            _LOGGER.debug("Successfully logged in")
            return True

    async def async_get_locations(self):
        try:
            raw_res = requests.get(LOCATIONS_URL, headers=self._headers, 
                cookies=self._cookies, timeout=self._timeout)
            locations = raw_res.json()
            _LOGGER.debug("Found %s locations: %s", len(locations), locations)
             
        except OSError:
            raise PyNeviwebError("Cannot get locations...")
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        locations = []
        response = raw_res.json()
        for location in response:
            locations.append(
                NeviwebLocation(
                    location["id"], 
                    location["name"], 
                    location["mode"]))
        
        return locations

    async def async_get_location_devices(self, locationId):
        """Get all devices linked to a specific location."""
        # Http request
        try:
            raw_res = requests.get(GATEWAY_DEVICE_URL + str(locationId),
                headers=self._headers, cookies=self._cookies, 
                timeout=self._timeout)
            devices = raw_res.json()
            _LOGGER.debug("Found %s devices in location %s: %s", len(devices),
                locationId, devices)
        except OSError:
            raise PyNeviwebError("Cannot get devices for location %s", 
                locationId)
        # Update cookies
        self._cookies.update(raw_res.cookies)
        
        for device in devices:
            data = self.get_device_attributes(device["id"], [ATTR_SIGNATURE])
            if ATTR_SIGNATURE in data:
                device[ATTR_SIGNATURE] = data[ATTR_SIGNATURE]
        _LOGGER.debug("Updated location devices: %s", devices)

        return devices

    def get_device_attributes(self, device_id, attributes):
        """Get device attributes."""
        # Prepare return
        data = {}
        # Http request
        try:
            raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
                "/attribute?attributes=" + ",".join(attributes), 
                headers=self._headers, cookies=self._cookies,
                timeout=self._timeout)
        except requests.exceptions.ReadTimeout:
            return {"errorCode": "ReadTimeout"}
        except Exception as e:
            raise PyNeviwebError("Cannot get device attributes", e)
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        data = raw_res.json()
        if "error" in data:
            if data["error"]["code"] == "USRSESSEXP":
                _LOGGER.error("Session expired. Set a scan_interval less" +
                "than 10 minutes, otherwise the session will end.")
                raise PyNeviwebError("Session expired")
        return data

    def get_device_daily_stats(self, device_id):
        """Get device power consumption (in Wh) for the last 30 days."""
        # Prepare return
        data = {}
        # Http request
        try:
            raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
                    "/statistics/30days", headers=self._headers,
                    cookies=self._cookies, timeout=self._timeout)
            _LOGGER.debug("Devices daily stat for %s: %s", device_id, raw_res.json())
        except OSError:
            raise PyNeviwebError("Cannot get device daily stats")
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        data = raw_res.json()
        if "values" in data:
            return data["values"]
        return []

    def get_device_hourly_stats(self, device_id):
        """Get device power consumption (in Wh) for the last 24 hours."""
        # Prepare return
        data = {}
        # Http request
        try:
            raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
                "/statistics/24hours", headers=self._headers,
                cookies=self._cookies, timeout=self._timeout)
        except OSError:
            raise PyNeviwebError("Cannot get device hourly stats")
        # Update cookies
        self._cookies.update(raw_res.cookies)
        # Prepare data
        data = raw_res.json()
        if "values" in data:
            return data["values"]
        return []

    def set_brightness(self, device_id, brightness):
        """Set device brightness."""
        data = {ATTR_INTENSITY: brightness}
        self.set_device_attributes(device_id, data)

    def set_mode(self, device_id, mode):
        """Set device operation mode."""
        data = {ATTR_POWER_MODE: mode}
        self.set_device_attributes(device_id, data)

    def set_setpoint_mode(self, device_id, mode):
        """Set thermostat operation mode."""
        data = {ATTR_SETPOINT_MODE: mode}
        self.set_device_attributes(device_id, data)

    def set_temperature(self, device_id, temperature):
        """Set device temperature."""
        data = {ATTR_ROOM_SETPOINT: temperature}
        self.set_device_attributes(device_id, data)

    def set_device_attributes(self, device_id, data):
        try:
            requests.put(DEVICE_DATA_URL + str(device_id) + "/attribute",
                data=data, headers=self._headers, cookies=self._cookies,
                timeout=self._timeout)
        except OSError:
            raise PyNeviwebError("Cannot set device %s attributes: %s", 
                device_id, data)
