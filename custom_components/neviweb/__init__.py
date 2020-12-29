import logging
from datetime import timedelta
from ratelimit import limits, sleep_and_retry

from homeassistant.const import (CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from .const import (DOMAIN, ATTR_INTENSITY, ATTR_POWER_MODE, 
    ATTR_OCCUPANCY_MODE, ATTR_SETPOINT_MODE, ATTR_ROOM_SETPOINT, 
    ATTR_SIGNATURE, NEVIWEB_PLATFORMS, DEFAULT_SCAN_INTEVAL)

#REQUIREMENTS = ['PY_Sinope==0.1.5']
VERSION = '1.2.5'


_LOGGER = logging.getLogger(__name__)

API_URL = "https://neviweb.com/api"
LOGIN_URL = "{}/login".format(API_URL)
LOCATIONS_URL = "{}/locations".format(API_URL)
GATEWAY_DEVICE_URL = "{}/devices?location$id=".format(API_URL)
DEVICE_DATA_URL = "{}/device/".format(API_URL)
HTTP_GET = "GET"
HTTP_POST = "POST"
HTTP_PUT = "PUT"
RATELIMIT_PER_SECOND = 10

async def async_setup(hass, hass_config):
    """Set up neviweb."""
    _LOGGER.debug("async_setup init.py")
    config = hass_config.get(DOMAIN, {})
    if config:
        _LOGGER.error("Neviweb must now be setup via Configuration / \
        Integrations menu. Please remove your existing yaml config and \
        restart Home Assistant.")
        return False
    return True

async def async_setup_entry(hass, entry):
    """Set up neviweb via a config entry."""
    _LOGGER.debug("async_setup_entry init.py")
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    client = NeviwebClient(session, email, password)
    await client.async_login()

    locations = await client.async_get_locations()
    devices = []
    for location_id in locations:
        devices += await client.async_get_location_devices(location_id)
    if len(devices) == 0:
        _LOGGER.error("No neviweb devices found.")
        return False
    
    data = NeviwebData(client, locations, devices)
    hass.data[DOMAIN] = data

    global SCAN_INTERVAL
    SCAN_INTERVAL = timedelta(seconds=entry.data.get(CONF_SCAN_INTERVAL, 
        DEFAULT_SCAN_INTEVAL))
    _LOGGER.debug("Setting scan interval to: %s", SCAN_INTERVAL)

    for platform in NEVIWEB_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
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

class NeviwebLocation(object):
    def __init__(self, location_data):
        self.id = location_data.get("id")
        self.name = location_data.get("name")
        self.mode = location_data.get("mode")

class NeviwebDeviceInfo(object):
    def __init__(self, device_info: dict):
        self.id = device_info.get("id")
        self.identifier = device_info.get("identifier")
        self.name = device_info.get("name")
        self.vendor = device_info.get("vendor")
        self.sku = device_info.get("sku")
        self.software_version = "{}.{}.{}".format(
            device_info["signature"]["softVersion"]["major"],
            device_info["signature"]["softVersion"]["middle"],
            device_info["signature"]["softVersion"]["minor"])

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
        
        locations = {}
        for location_data in response:
            locations[location_data["id"]] = NeviwebLocation(location_data)

        return locations

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
            