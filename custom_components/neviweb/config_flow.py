"""Config flow for neviweb integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from . import NeviwebClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # session = hass.helpers.aiohttp_client.async_get_clientsession()
    # client = NeviwebClient(session, data[CONF_EMAIL], data[CONF_PASSWORD])
    # await client.async_login()

    # try:
    #     await AsyncGriddy(
    #         client_session, settlement_point=data[CONF_LOADZONE]
    #     ).async_getnow()
    # except (asyncio.TimeoutError, ClientError) as err:
    #     raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return 

@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for neviweb."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            # except CannotConnect:
            #     errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)

        return self.async_show_form(
            step_id="user", 
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str
            })
        )