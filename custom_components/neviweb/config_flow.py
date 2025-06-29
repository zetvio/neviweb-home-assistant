"""Config flow for neviweb integration."""
import logging
import asyncio
from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import NeviwebClient, PyNeviwebError
from .const import DOMAIN, DEFAULT_SCAN_INTEVAL

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTEVAL): int,
    }
)


async def async_validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = NeviwebClient(session, data[CONF_EMAIL], data[CONF_PASSWORD])
    await client.async_login()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for neviweb."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            try:
                await async_validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )
            except (asyncio.TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except PyNeviwebError:
                _LOGGER.error("Authentication failed for neviweb")
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )