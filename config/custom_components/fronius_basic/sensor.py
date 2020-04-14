"""Support for the Fronius Basic."""


#-----------------------------------------------------  python libraries  ---------------------------------------------------------

import logging
from datetime import timedelta

import requests
import voluptuous as vol
import json

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, ATTR_ATTRIBUTION, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
    )
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow as dt_utcnow, as_local
from homeassistant.helpers.sun import get_astral_event_date




'''--------------------------------------------------------------------------------------------------------------------------------

                                                       CONSTANTS DEFINITIONS

--------------------------------------------------------------------------------------------------------------------------------'''

_POWERFLOW_URL = 'http://{}/solar_api/v1/GetPowerFlowRealtimeData.fcgi'
_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Fronius Inverter Basic Data"

CONF_NAME = 'name'
CONF_IP_ADDRESS = 'ip_address'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)

# Key: ['json_key', 'name', 'unit', 'convert_units', 'icon']
SENSOR_LIST = {
    'grid_injection':  ['P_Grid', 'Grid Injection', 'W', 'power_negative', 'mdi:solar-power'],
    'house_load': ['P_Load', 'House Load', 'W', 'power_negative', 'mdi:solar-power'],
    'solar': ['P_PV', 'Solar', 'W', 'power', 'mdi:solar-panel'],
    'energy_today': ['E_Day', 'Energy Today', 'kWh', 'energy', 'mdi:solar-panel'],
    'self_consumption': ['rel_SelfConsumption', 'Self Consumption', '%', False, 'mdi:solar-panel']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default='Fronius'): cv.string,
})




'''--------------------------------------------------------------------------------------------------------------------------------

                                                         CLASS DEFINITIONS

--------------------------------------------------------------------------------------------------------------------------------'''

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Fronius inverter sensor."""

    ip_address = config[CONF_IP_ADDRESS]
    name = config.get(CONF_NAME)

    smartmeter = PowerflowData(ip_address)
    try:
        await smartmeter.async_update()
    except ValueError as err:
        _LOGGER.error("Received data error from Fronius SmartMeter: %s", err)
        return

    dev = []
    for sensor_key in SENSOR_LIST:
        sensor = "sensor." + name + "_" + SENSOR_LIST[sensor_key][1]
        state = hass.states.get(sensor)
        _LOGGER.debug("Adding SmartMeter sensor: {}, {}".format(name, sensor_key))
        dev.append(FroniusSensor(smartmeter, name, sensor_key))

    for inverter in smartmeter.latest_data_inverters:
        sensor = "sensor." + name + "_inverter_" + inverter
        state = hass.states.get(sensor)
        _LOGGER.debug("Adding Fronius sensor: Inverter {}".format(inverter))
        dev.append(FroniusSensor(smartmeter, name, inverter))

    async_add_entities(dev, True)

#   async_setup_platform
#----------------------------------------------------------------------------------------------------------------------------------


class FroniusSensor(Entity):
    """Implementation of the Fronius inverter sensor."""

    def __init__(self, smartmeter, name, sensor_key):
        """Initialize the sensor."""
        self._smartmeter = smartmeter
        self._client = name
        self._sensor_key = sensor_key
        if self._sensor_key.isnumeric():
            self._json_key = 'P'
            self._name = 'Inverter ' + sensor_key
            self._unit = 'W'
            self._convert_units = 'power'
            self._icon = 'mdi:solar-panel'
        else:
            self._json_key = SENSOR_LIST[sensor_key][0]
            self._name = SENSOR_LIST[sensor_key][1]
            self._unit = SENSOR_LIST[sensor_key][2]
            self._convert_units = SENSOR_LIST[sensor_key][3]
            self._icon = SENSOR_LIST[sensor_key][4]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self, utcnow=None):
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    async def async_update(self, utcnow=None):
        """Get the latest data from inverter and update the states."""

        # Prevent errors when data not present at night but retain long term states
        await self._smartmeter.async_update()
        if not self._smartmeter:
            _LOGGER.error("Didn't receive data from the inverter")
            return

        state = None
        if self._sensor_key.isnumeric():
            if self._smartmeter.latest_data_inverters:
                _LOGGER.debug("Sensor: inverter {}".format(self._sensor_key))
                # Read data
                if self._smartmeter.latest_data_inverters[self._sensor_key][self._json_key]:
                    state = self._smartmeter.latest_data_inverters[self._sensor_key][self._json_key]
                _LOGGER.debug("State: {}".format(state))
        else:
            if self._smartmeter.latest_data_site and (self._json_key in self._smartmeter.latest_data_site):
                _LOGGER.debug("Sensor: {}".format(self._sensor_key))
                # Read data
                if self._smartmeter.latest_data_site[self._json_key]:
                    state = self._smartmeter.latest_data_site[self._json_key]
                _LOGGER.debug("State: {}".format(state))

        # convert and round the result
        if state is not None:
            if self._convert_units == "energy":
                _LOGGER.debug("Converting energy ({}) to kWh".format(state))
                self._state = round(state / 1000, 2)
            elif self._convert_units == "power":
                _LOGGER.debug("Converting power ({}) to W".format(state))
                self._state = int(round(state, 0))
            elif self._convert_units == "power_negative":
                _LOGGER.debug("Converting power ({}) to W".format(state))
                self._state = int(round(-state, 0))
            else:
                _LOGGER.debug("Rounding ({}) to zero decimals".format(state))
                self._state = int(round(state, 0))
        else:
            self._state = 0
        _LOGGER.debug("State converted ({})".format(self._state))

#   FroniusSensor
#----------------------------------------------------------------------------------------------------------------------------------


class PowerflowData:
    """Handle Fronius API object and limit updates."""

    def __init__(self, ip_address):
        """Initialize the data object."""
        self._ip_address = ip_address

    def _build_url(self):
        """Build the URL for the requests."""
        url = _POWERFLOW_URL.format(self._ip_address)
        _LOGGER.debug("Fronius Powerflow URL: %s", url)
        return url

    @property
    def latest_data_site(self):
        """Return the latest data object."""
        if self._site:
            return self._site
        return None

    @property
    def latest_data_inverters(self):
        """Return the latest data object."""
        if self._inverters:
            return self._inverters
        return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from inverter."""
        try:
            result = requests.get(self._build_url(), timeout=10).json()
            self._site = result['Body']['Data']['Site']
            self._inverters = result['Body']['Data']['Inverters']
        except (requests.exceptions.RequestException) as error:
            _LOGGER.error("Unable to connect to Powerflow: %s", error)
            self._site = None
            self._inverters = None

#   PowerflowData
#----------------------------------------------------------------------------------------------------------------------------------




#------------------------------------------------------  END OF DOCUMENT  ---------------------------------------------------------
