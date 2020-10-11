import logging
import requests
import json
import aiohttp
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
API_URL = "https://neviweb.com/api"
LOGIN_URL = "{}/login".format(API_URL)
LOCATIONS_URL = "{}/locations".format(API_URL)
GATEWAY_DEVICE_URL = "{}/devices?location$id=".format(API_URL)
DEVICE_DATA_URL = "{}/device/".format(API_URL)
HTTP_GET = "GET"
HTTP_POST = "POST"
HTTP_PUT = "PUT"

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

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    client = NeviwebClient(session, email, password)
    await client.async_login()

    locations = await client.async_get_locations()
    devices = await locations.async_get_all_locations_devices(client)

    data = NeviwebData(client, locations, devices)
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

    return True

class NeviwebData:

    def __init__(self, client, locations, devices):
        """Init the neviweb data object."""
        # from pyneviweb import NeviwebClient
        self.neviweb_client = client
        self.locations = locations
        self.devices = devices


# According to HA: 
# https://developers.home-assistant.io/docs/en/creating_component_code_review.html
# "All API specific code has to be part of a third party library hosted on PyPi. 
# Home Assistant should only interact with objects and not make direct calls to the API."
# So all code below this line should eventually be integrated in a PyPi project.

#from PY_Sinope import pyneviweb

class PyNeviwebError(Exception):
    pass

class NeviwebLocations(object):
    def __init__(self, data):
        self.data = data

    async def async_get_all_locations_devices(self, client):
        devices = []
        for location in self.data:
            devices += await client.async_get_location_devices(location["id"])

        return devices

class NeviwebClient(object):

    def __init__(self, session, email, password, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self._session = session
        self._email = email
        self._password = password
        self._headers = {}
        self._cookies = None
        self._timeout = timeout
        self.user = None      

    # async def async_update(self):
    #     await self.__async_get_gateway_data()

    async def async_login(self):
        url = API_URL + "/login"
        json = {
            "username": self._email, 
            "password": self._password, 
            "interface": "neviweb", 
            "stayConnected": 1
        }
        response = await self._async_http_request(HTTP_POST, url, json=json)
        self._headers["Session-Id"] = response["session"]

    # async def async_post_login_page(self):
    #     """Login to Neviweb."""
    #     data = {"username": self._email, "password": self._password, 
    #         "interface": "neviweb", "stayConnected": 1}
    #     try:
    #         raw_res = requests.post(LOGIN_URL, data=data, 
    #             cookies=self._cookies, allow_redirects=False, 
    #             timeout=self._timeout)
    #     except OSError:
    #         raise PyNeviwebError("Cannot submit login form")
    #     if raw_res.status_code != 200:
    #         raise PyNeviwebError("Cannot log in")

    #     # Update session
    #     self._cookies = raw_res.cookies
    #     data = raw_res.json()
    #     _LOGGER.debug("Login response: %s", data)
    #     if "error" in data:
    #         if data["error"]["code"] == "ACCSESSEXC":
    #             _LOGGER.error("Too many active sessions. Close all Neviweb " +
    #             "sessions you have opened on other platform (mobile, browser" +
    #             ", ...), wait a few minutes, then reboot Home Assistant.")
    #         return False
    #     else:
    #         self.user = data["user"]
    #         self._headers = {"Session-Id": data["session"]}
    #         _LOGGER.debug("Successfully logged in")
    #         return True

    # async def async_get_locations(self):
    #     try:
    #         raw_res = requests.get(LOCATIONS_URL, headers=self._headers, 
    #             cookies=self._cookies, timeout=self._timeout)
    #         locations = raw_res.json()
    #         _LOGGER.debug("Found %s locations: %s", len(locations), locations)
             
    #     except OSError:
    #         raise PyNeviwebError("Cannot get locations...")
    #     # Update cookies
    #     self._cookies.update(raw_res.cookies)
        
    #     return NeviwebLocations(raw_res.json())

    async def async_get_locations(self):
        url = API_URL + "/locations"
        response = await self._async_http_request(HTTP_GET, url)
        return NeviwebLocations(response)

    async def async_get_location_devices(self, location_id):
        url = API_URL + "/devices"
        params = {
            "location$id": location_id
        }
        devices = await self._async_http_request(HTTP_GET, url, params=params)

        for device in devices:
            attributes = await self.async_get_device_attributes(device["id"], 
                [ATTR_SIGNATURE])
            if ATTR_SIGNATURE in attributes:
                device[ATTR_SIGNATURE] = attributes[ATTR_SIGNATURE]
        _LOGGER.debug("Updated location devices: %s", devices)

        return devices

    # async def async_get_location_devices(self, locationId):
    #     """Get all devices linked to a specific location."""
    #     # Http request
    #     try:
    #         raw_res = requests.get(GATEWAY_DEVICE_URL + str(locationId),
    #             headers=self._headers, cookies=self._cookies, 
    #             timeout=self._timeout)
    #         devices = raw_res.json()
    #         _LOGGER.debug("Found %s devices in location %s: %s", len(devices),
    #             locationId, devices)
    #     except OSError:
    #         raise PyNeviwebError("Cannot get devices for location %s", 
    #             locationId)
    #     # Update cookies
    #     self._cookies.update(raw_res.cookies)
        
    #     for device in devices:
    #         data = await self.async_get_device_attributes(device["id"], [ATTR_SIGNATURE])
    #         if ATTR_SIGNATURE in data:
    #             device[ATTR_SIGNATURE] = data[ATTR_SIGNATURE]
    #     _LOGGER.debug("Updated location devices: %s", devices)

    #     return devices

    async def async_get_device_attributes(self, device_id, attributes):
        url = API_URL + f"/device/{device_id}/attribute"
        params = {
            "attributes": ",".join(attributes)
        }
        return await self._async_http_request(HTTP_GET, url, params=params) 
    
    # async def async_get_device_attributes(self, device_id, attributes):
    #     """Get device attributes."""
    #     # Prepare return
    #     data = {}
    #     # Http request
    #     try:
    #         raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
    #             "/attribute?attributes=" + ",".join(attributes), 
    #             headers=self._headers, cookies=self._cookies,
    #             timeout=self._timeout)
    #     except requests.exceptions.ReadTimeout:
    #         return {"errorCode": "ReadTimeout"}
    #     except Exception as e:
    #         raise PyNeviwebError("Cannot get device attributes", e)
    #     # Update cookies
    #     self._cookies.update(raw_res.cookies)
    #     # Prepare data
    #     data = raw_res.json()
    #     if "error" in data:
    #         if data["error"]["code"] == "USRSESSEXP":
    #             _LOGGER.error("Session expired. Set a scan_interval less" +
    #             "than 10 minutes, otherwise the session will end.")
    #             raise PyNeviwebError("Session expired")
    #     return data

    async def async_get_device_daily_stats(self, device_id):
        url = API_URL + f"/device/{device_id}/statistics/30days"
        response = await self._async_http_request(HTTP_GET, url)
        if "values" in response:
            return response["values"]
        return []

    # async def async_get_device_daily_stats(self, device_id):
    #     """Get device power consumption (in Wh) for the last 30 days."""
    #     # Prepare return
    #     data = {}
    #     # Http request
    #     try:
    #         raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
    #                 "/statistics/30days", headers=self._headers,
    #                 cookies=self._cookies, timeout=self._timeout)
    #         _LOGGER.debug("Devices daily stat for %s: %s", device_id, raw_res.json())
    #     except OSError:
    #         raise PyNeviwebError("Cannot get device daily stats")
    #     # Update cookies
    #     self._cookies.update(raw_res.cookies)
    #     # Prepare data
    #     data = raw_res.json()
    #     if "values" in data:
    #         return data["values"]
    #     return []

    async def async_get_device_hourly_stats(self, device_id):
        url = API_URL + f"/device/{device_id}/statistics/24hours"
        response = await self._async_http_request(HTTP_GET, url)
        if "values" in response:
            return response["values"]
        return []


    # async def async_get_device_hourly_stats(self, device_id):
    #     """Get device power consumption (in Wh) for the last 24 hours."""
    #     # Prepare return
    #     data = {}
    #     # Http request
    #     try:
    #         raw_res = requests.get(DEVICE_DATA_URL + str(device_id) +
    #             "/statistics/24hours", headers=self._headers,
    #             cookies=self._cookies, timeout=self._timeout)
    #     except OSError:
    #         raise PyNeviwebError("Cannot get device hourly stats")
    #     # Update cookies
    #     self._cookies.update(raw_res.cookies)
    #     # Prepare data
    #     data = raw_res.json()
    #     if "values" in data:
    #         return data["values"]
    #     return []

    async def async_set_brightness(self, device_id, brightness):
        """Set device brightness."""
        data = {ATTR_INTENSITY: brightness}
        await self.async_set_device_attributes(device_id, data)

    async def async_set_mode(self, device_id, mode):
        """Set device operation mode."""
        data = {ATTR_POWER_MODE: mode}
        await self.async_set_device_attributes(device_id, data)

    async def async_set_setpoint_mode(self, device_id, mode):
        """Set thermostat operation mode."""
        data = {ATTR_SETPOINT_MODE: mode}
        await self.async_set_device_attributes(device_id, data)

    async def async_set_temperature(self, device_id, temperature):
        """Set device temperature."""
        data = {ATTR_ROOM_SETPOINT: temperature}
        await self.async_set_device_attributes(device_id, data)

    async def async_set_device_attributes(self, device_id, data):
        url = API_URL + f"/device/{device_id}/attribute"
        return await self._async_http_request(HTTP_PUT, url, data=data)

    # async def async_set_device_attributes(self, device_id, data):
    #     try:
    #         requests.put(DEVICE_DATA_URL + str(device_id) + "/attribute",
    #             data=data, headers=self._headers, cookies=self._cookies,
    #             timeout=self._timeout)
    #     except OSError:
    #         raise PyNeviwebError("Cannot set device %s attributes: %s", 
    #             device_id, data)

    async def _async_http_request(self, method, url, params=None, json=None,
        data=None):
        _LOGGER.debug("%s %s params=%s, json=%s, data=%s", method, url, 
            params, json, data)
        async with self._session.request(
            method, url, headers=self._headers, params=params, json=json,
            data=data) as resp:
            assert resp.status == 200
            _LOGGER.debug("response: %s", resp)
            ret = await resp.json()
            _LOGGER.debug("response json: %s", ret)
            return ret

    # async def _get_resource(self, resource, retries=3):
    #     try:
    #         if self.session and not self.session.closed:
    #             return await self._run_get_resource(resource)
    #         async with ClientSession() as self.session:
    #             return await self._run_get_resource(resource)
    #     except ServerDisconnectedError as error:
    #         _LOGGER.debug("ServerDisconnectedError %d", retries)
    #         if retries == 0:
    #             raise error