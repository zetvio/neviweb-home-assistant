"""Constants for neviweb component."""

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

DOMAIN = "neviweb"
CONF_NETWORK = 'network'
CONF_NETWORK2 = 'network2'

NEVIWEB_PLATFORMS = ["climate", "light", "switch"]

ATTR_SIGNATURE = "signature"
ATTR_POWER_MODE = "powerMode"
ATTR_INTENSITY = "intensity"
ATTR_RSSI = "rssi"
ATTR_WATTAGE = "wattage"
ATTR_WATTAGE_INSTANT = "wattageInstant"
ATTR_WATTAGE_OVERRIDE = "wattageOverride"
ATTR_SETPOINT_MODE = "setpointMode"
ATTR_ROOM_SETPOINT = "roomSetpoint"
ATTR_ROOM_TEMPERATURE = "roomTemperature"
ATTR_OUTPUT_PERCENT_DISPLAY = "outputPercentDisplay"
ATTR_ROOM_SETPOINT_MIN = "roomSetpointMin"
ATTR_ROOM_SETPOINT_MAX = "roomSetpointMax"
ATTR_OCCUPANCY_MODE = "occupancyMode"
ATTR_SERVICE_OPERATION_MODE = "operation_mode"
ATTR_SERVICE_OCCUPANCY_MODE = "occupancy_mode"

MODE_AUTO = "auto"
MODE_AUTO_BYPASS = "autoBypass"
MODE_MANUAL = "manual"
MODE_AWAY = "away"
MODE_OFF = "off"
MODE_HOME = "home"

SERVICE_SET_LIGHT_OPERATION_MODE = "set_light_operation_mode"
SERVICE_SET_LIGHT_OCCUPANCY_MODE = "set_light_occupancy_mode"
SERVICE_SET_SWITCH_OPERATION_MODE = "set_switch_operation_mode"
SERVICE_SET_SWITCH_OCCUPANCY_MODE = "set_switch_occupancy_mode"

SERVICE_SET_OPERATION_MODE_SCHEMA = {
    vol.Required(ATTR_SERVICE_OPERATION_MODE): 
       vol.Any(MODE_AUTO, MODE_MANUAL)
}

SERVICE_SET_OCCUPANCY_MODE_SCHEMA = {
    vol.Required(ATTR_SERVICE_OCCUPANCY_MODE): 
        vol.Any(MODE_HOME, MODE_AWAY)
}
