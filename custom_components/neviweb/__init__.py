import logging
from datetime import timedelta
from ratelimit import limits, sleep_and_retry

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_USERNAME, CONF_EMAIL, CONF_PASSWORD,
    CONF_SCAN_INTERVAL)
from .const import (DOMAIN, CONF_NETWORK, CONF_NETWORK2, ATTR_INTENSITY, 
    ATTR_POWER_MODE, ATTR_OCCUPANCY_MODE, ATTR_SETPOINT_MODE, 
    ATTR_ROOM_SETPOINT, ATTR_SIGNATURE)

#REQUIREMENTS = ['PY_Sinope==0.1.5']
VERSION = '1.2.5'


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=540)

API_URL = "https://neviweb.com/api"
LOGIN_URL = "{}/login".format(API_URL)
LOCATIONS_URL = "{}/locations".format(API_URL)
GATEWAY_DEVICE_URL = "{}/devices?location$id=".format(API_URL)
DEVICE_DATA_URL = "{}/device/".format(API_URL)
HTTP_GET = "GET"
HTTP_POST = "POST"
HTTP_PUT = "PUT"
RATELIMIT_PER_SECOND = 10

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

    def __init__(self, session, email, password):
        """Initialize the client object."""
        self._session = session
        self._email = email
        self._password = password
        self._headers = {}

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

    async def async_get_locations(self):
        url = API_URL + "/locations"
        response = await self._async_http_request(HTTP_GET, url)
        _LOGGER.debug("Found %s location(s): %s", len(response), response)
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
        _LOGGER.debug("Found %s device(s) in location %s: %s", len(devices),
            location_id, devices)

        return devices

    async def async_get_device_attributes(self, device_id, attributes):
        url = API_URL + f"/device/{device_id}/attribute"
        params = {
            "attributes": ",".join(attributes)
        }
        return await self._async_http_request(HTTP_GET, url, params=params) 

    async def async_get_device_daily_stats(self, device_id):
        url = API_URL + f"/device/{device_id}/statistics/30days"
        response = await self._async_http_request(HTTP_GET, url)
        _LOGGER.debug("Daily stats for %s: %s", device_id, response)
        if "values" in response:
            return response["values"]
        return []

    async def async_get_device_hourly_stats(self, device_id):
        url = API_URL + f"/device/{device_id}/statistics/24hours"
        response = await self._async_http_request(HTTP_GET, url)
        _LOGGER.debug("Hourly stats for %s: %s", device_id, response)
        if "values" in response:
            return response["values"]
        return []

    async def async_set_brightness(self, device_id, brightness):
        """Set device brightness."""
        data = {ATTR_INTENSITY: brightness}
        await self.async_set_device_attributes(device_id, data)

    async def async_set_operation_mode(self, device_id, mode):
        """Set device operation mode."""
        data = {ATTR_POWER_MODE: mode}
        await self.async_set_device_attributes(device_id, data)

    async def async_set_occupancy_mode(self, device_id, mode):
        """Set device occupancy mode."""
        data = {ATTR_OCCUPANCY_MODE: mode}
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
        _LOGGER.debug("Setting device %s attributes: %s", device_id, data)
        return await self._async_http_request(HTTP_PUT, url, data=data)

    @sleep_and_retry
    @limits(calls=RATELIMIT_PER_SECOND, period=1)
    async def _async_http_request(self, method, url, params=None, json=None,
        data=None):
        # _LOGGER.debug("%s %s params=%s, json=%s, data=%s", method, url, 
        #     params, json, data)
        async with self._session.request(
            method, url, headers=self._headers, params=params, json=json,
            data=data) as resp:
            if resp.status != 200:
                _LOGGER.error("Bad response status %s", resp)
                raise PyNeviwebError("Bad response status")
            ret = await resp.json()
            # _LOGGER.debug("response json: %s", ret)
            self._handle_errors(ret)
            return ret

    def _handle_errors(self, response):
        if "error" in response:
            error_code = response["error"]["code"]
            if error_code == "USRSESSEXP":
                _LOGGER.error("Session expired. Set a scan_interval less" +
                "than 10 minutes, otherwise the session will end. %s",
                response)
                raise PyNeviwebError("Session expired")
            if error_code == "ACCSESSEXC":
                _LOGGER.error("Too many active sessions. Close all Neviweb " +
                "sessions you have opened on other platform (mobile, browser" +
                ", ...), wait a few minutes, then reboot Home Assistant. %s",
                response)
                raise PyNeviwebError("Too many sessions")
            # raise PyNeviwebError(f"Unknown neviweb error: {error_code}")
            