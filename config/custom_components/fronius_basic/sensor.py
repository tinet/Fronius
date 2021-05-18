"""Support for the Fronius Basic."""


#-----------------------------------------------------  python libraries  ---------------------------------------------------------
import logging
import time
from datetime import timedelta
import inspect
import os.path

import requests
import voluptuous as vol
import json
import aiohttp

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_SCAN_INTERVAL, ATTR_ATTRIBUTION
    )
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import now as dt_now




'''--------------------------------------------------------------------------------------------------------------------------------

                                                       CONSTANTS DEFINITIONS

--------------------------------------------------------------------------------------------------------------------------------'''

_POWERFLOW_URL = 'http://{}/solar_api/v1/GetPowerFlowRealtimeData.fcgi'
_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Fronius Inverter Basic Data"

CONF_NAME = 'name'
CONF_IP_ADDRESS = 'ip_address'

DEFAULT_SCAN_INTERVAL = timedelta(seconds=4)

# Key: ['device', 'system', 'json_key', 'name', 'unit', 'convert_units', 'icon']
SENSOR_LIST = {
    'pv_power': ['P_PV', 'PV power', 'W', 'Power', 'mdi:gauge'],
    'grid_power': ['P_Grid', 'Grid Power', 'W', 'power', 'mdi:gauge'],
    'house_power': ['P_Load', 'House Power', 'W', 'power_negative', 'mdi:gauge'],

    'self_sufficiency': ['rel_Autonomy', 'Self Sufficiency', '%', False, 'mdi:brightness-percent'],
    'self_consumption': ['rel_SelfConsumption', 'Self Consumption', '%', False, 'mdi:brightness-percent'],

    'pv_energy_today': ['E_Day', 'PV Energy Today', 'kWh', 'energy3', 'mdi:transmission-tower'],
    'pv_energy_year': ['E_Year', 'PV Energy Year', 'kWh', 'energy', 'mdi:transmission-tower'],
    'pv_energy_total': ['E_Total', 'PV Energy Total', 'kWh', 'energy', 'mdi:transmission-tower'],

    'grid_energy_hour': ['grid_energy_hour', 'Grid Energy Hour', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'grid_energy_today': ['grid_energy_today', 'Grid Energy Today', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'grid_energy_month': ['grid_energy_month', 'Grid Energy Month', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'grid_energy_total': ['grid_energy_total', 'Grid Energy Total', 'kWh', 'energy_float', 'mdi:transmission-tower'],

    'house_energy_hour': ['house_energy_hour', 'House Energy Hour', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'house_energy_today': ['house_energy_today', 'House Energy Today', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'house_energy_month': ['house_energy_month', 'House Energy Month', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'house_energy_total': ['house_energy_total', 'House Energy Total', 'kWh', 'energy_float', 'mdi:transmission-tower'],

    'grid_returned_energy_hour': ['grid_returned_energy_hour', 'Grid Returned Energy Hour', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'grid_returned_energy_today': ['grid_returned_energy_today', 'Grid Returned Energy Today', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'grid_returned_energy_month': ['grid_returned_energy_month', 'Grid Returned Energy Month', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'grid_returned_energy_total': ['grid_returned_energy_total', 'Grid Returned Energy Total', 'kWh', 'energy_float', 'mdi:transmission-tower'],

    'balance_neto_hour': ['balance_neto_hour', 'Balance Neto Hour', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'balance_neto_today': ['balance_neto_today', 'Balance Neto Today', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'balance_neto_month': ['balance_neto_month', 'Balance Neto Month', 'kWh', 'energy_float', 'mdi:transmission-tower'],
    'balance_neto_total': ['balance_neto_total', 'Balance Neto Total', 'kWh', 'energy_float', 'mdi:transmission-tower'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default='Fronius'): cv.string,
})




'''--------------------------------------------------------------------------------------------------------------------------------

                                                         VARIABLE DEFINITIONS

--------------------------------------------------------------------------------------------------------------------------------'''

start_time = time.time()




'''--------------------------------------------------------------------------------------------------------------------------------

                                                         CLASS DEFINITIONS

--------------------------------------------------------------------------------------------------------------------------------'''

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Fronius inverter sensor."""

    _LOGGER.debug("-->{}s {}() ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))
    session = async_get_clientsession(hass)
    ip_address = config[CONF_IP_ADDRESS]
    name = config.get(CONF_NAME)
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    fetchers = []
    powerflow_data = PowerflowData(session, ip_address)
    fetchers.append(powerflow_data)

    def fetch_executor(fetcher):
        async def fetch_data(*_):
            await fetcher.async_update()
        return fetch_data
    
    for fetcher in fetchers:
        fetch = fetch_executor(fetcher)
        await fetch()
        async_track_time_interval(hass, fetch, scan_interval)

    dev = []
    for sensor_key in SENSOR_LIST:
        sensor = "sensor." + name + "_" + SENSOR_LIST[sensor_key][1]
        state = hass.states.get(sensor)
        dev.append(FroniusSensor(powerflow_data, name, sensor_key))

    for inverter in powerflow_data.latest_inverters:
        sensor = "sensor." + name + "_inverter" + inverter + '_power'
        state = hass.states.get(sensor)
        dev.append(FroniusSensor(powerflow_data, name, inverter))

    async_add_entities(dev, True)
    _LOGGER.debug("<--{}s {}() ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))

#   async_setup_platform
#----------------------------------------------------------------------------------------------------------------------------------


class FroniusSensor(Entity):
    """Implementation of the Fronius inverter sensor."""

    def __init__(self, device_data, name, sensor_key):
        """Initialize the sensor."""
        _LOGGER.debug("<->{}s {}({}) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, sensor_key, os.path.basename(__file__), inspect.currentframe().f_lineno))
        self._client = name
        self._sensor_key = sensor_key
        self._data = device_data
        self._state = None

        if sensor_key.isnumeric():
            self._json_key = 'P'
            self._name = 'Inverter' + sensor_key + ' Power'
            self._unit = 'W'
            self._convert_units = 'power'
            self._icon = 'mdi:gauge'
        else:
            self._json_key = SENSOR_LIST[sensor_key][0]
            self._name = SENSOR_LIST[sensor_key][1]
            self._unit = SENSOR_LIST[sensor_key][2]
            self._convert_units = SENSOR_LIST[sensor_key][3]
            self._icon = SENSOR_LIST[sensor_key][4]

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
    def unique_id(self):
        """Return the unique id."""
        return f"{self._client} {self._name}"

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

    @property
    def should_poll(self):
        """Device should not be polled, returns False."""
        return False

    async def async_update(self, utcnow=None):
        """Get the latest data from inverter and update the states."""
        _LOGGER.debug("<->{}s {}({}) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, self._sensor_key, os.path.basename(__file__), inspect.currentframe().f_lineno))
        state = None
        if self._sensor_key.isnumeric():
            if self._data.latest_inverters:
                # Read data
                state = self._data.latest_inverters[self._sensor_key][self._json_key]
                if state is None:
                    state = 0
        else:
            if self._data.latest_site:
                if self._json_key in self._data.latest_site:
                    # Read data directly, if it is 'null' convert it to 0
                    state = self._data.latest_site[self._json_key]
                    if state is None:
                        state = 0
                else:
                    if self._json_key == "grid_energy_hour":
                        state = self._data.grid_energy_hour
                    elif self._json_key == "grid_energy_today":
                        state = self._data.grid_energy_today
                    elif self._json_key == "grid_energy_month":
                        state = self._data.grid_energy_month
                    elif self._json_key == "grid_energy_total":
                        state = self._data.grid_energy_total

                    if self._json_key == "house_energy_hour":
                        state = self._data.house_energy_hour
                    elif self._json_key == "house_energy_today":
                        state = self._data.house_energy_today
                    elif self._json_key == "house_energy_month":
                        state = self._data.house_energy_month
                    elif self._json_key == "house_energy_total":
                        state = self._data.house_energy_total

                    elif self._json_key == "grid_returned_energy_hour":
                        state = self._data.grid_returned_energy_hour
                    elif self._json_key == "grid_returned_energy_today":
                        state = self._data.grid_returned_energy_today
                    elif self._json_key == "grid_returned_energy_month":
                        state = self._data.grid_returned_energy_month
                    elif self._json_key == "grid_returned_energy_total":
                        state = self._data.grid_returned_energy_total

                    elif self._json_key == "balance_neto_hour":
                        state = self._data.balance_neto_hour
                    elif self._json_key == "balance_neto_today":
                        state = self._data.balance_neto_today
                    elif self._json_key == "balance_neto_month":
                        state = self._data.balance_neto_month
                    elif self._json_key == "balance_neto_total":
                        state = self._data.balance_neto_total

        # convert and round the result
        if state is not None:
            if self._convert_units == "energy":
                self._state = int(round(state / 1000))
            elif self._convert_units == "energy3":
                self._state = round(state / 1000, 3)
            elif self._convert_units == "energy_float":
                self._state = round(state / 3600000, 3)
            elif self._convert_units == "power":
                self._state = int(round(state))
            elif self._convert_units == "power_negative":
                self._state = int(round(-state))
            else:
                self._state = int(round(state))

    async def async_added_to_hass(self):
        """Register at data provider for updates."""
        await self._data.register(self)

    def __hash__(self):
        """Hash sensor by hashing its name."""
        return hash(self.name)

#   FroniusSensor
#----------------------------------------------------------------------------------------------------------------------------------


class FroniusFetcher:
    """Handle Fronius API requests."""

    def __init__(self, session, ip_address):
        """Initialize the data object."""
        self._session = session
        self._ip_address = ip_address
        self._data = None
        self._sensors = set()
        self._day = dt_now().day
        self._hour = dt_now().hour
        self._month = dt_now().month
        self._latest_call = time.time()
        self._latest_grid_power = 0
        self._latest_house_power = 0

        self._grid_energy_hour = 0
        self._grid_energy_today = 0
        self._grid_energy_month = 0
        self._grid_energy_total = 0

        self._house_energy_hour = 0
        self._house_energy_today = 0
        self._house_energy_month = 0
        self._house_energy_total = 0

        self._grid_returned_energy_hour = 0
        self._grid_returned_energy_today = 0
        self._grid_returned_energy_month = 0
        self._grid_returned_energy_total = 0

        self._balance_neto_hour = 0
        self._balance_neto_today = 0
        self._balance_neto_month = 0
        self._balance_neto_total = 0

    async def async_update(self):
        """Retrieve and update latest state."""
        _LOGGER.debug("-->{}s {}(FroniusFetcher) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))
        try:
            await self._update()
        except aiohttp.ClientConnectionError:
            _LOGGER.error("    Failed to update: connection error ({}:{})".format(os.path.basename(__file__), inspect.currentframe().f_lineno))
        except asyncio.TimeoutError:
            _LOGGER.error("    Failed to update: request timeout ({}:{})".format(os.path.basename(__file__), inspect.currentframe().f_lineno))
        except ValueError:
            _LOGGER.error("    Failed to update: invalid response received ({}:{})".format(os.path.basename(__file__), inspect.currentframe().f_lineno))

        # Schedule an update for all included sensors
        for sensor in self._sensors:
            sensor.async_schedule_update_ha_state(True)
        _LOGGER.debug("<--{}s {}(FroniusFetcher) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))
    
    async def fetch_data(self, url):
        """Retrieve data from inverter in async manner."""
        _LOGGER.debug("-->{}s {}(FroniusFetcher) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))
        try:
            response = await self._session.get(url, timeout=10)
            if response.status != 200:
                raise ValueError
            json_response = await response.json()
            _LOGGER.debug("<--{}s {}(FroniusFetcher) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))
            return json_response
        except aiohttp.ClientResponseError:
            raise ValueError
        _LOGGER.debug("<--{}s {}(FroniusFetcher) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))

    @property
    def latest_inverters(self):
        """Return the latest data object."""
        if self._data:
            return self._data['Inverters']
        return None

    @property
    def latest_site(self):
        """Return the latest data object."""
        if self._data:
            return self._data['Site']
        return None

    @property
    def grid_energy_hour(self):
        """Return the grid energy."""
        return self._grid_energy_hour

    @property
    def grid_energy_today(self):
        """Return the grid energy."""
        return self._grid_energy_today

    @property
    def grid_energy_month(self):
        """Return the grid energy."""
        return self._grid_energy_month

    @property
    def grid_energy_total(self):
        """Return the grid energy."""
        return self._grid_energy_total

    @property
    def house_energy_hour(self):
        """Return the grid energy."""
        return self._house_energy_hour

    @property
    def house_energy_today(self):
        """Return the grid energy."""
        return self._house_energy_today

    @property
    def house_energy_month(self):
        """Return the grid energy."""
        return self._house_energy_month

    @property
    def house_energy_total(self):
        """Return the grid energy."""
        return self._house_energy_total

    @property
    def grid_returned_energy_hour(self):
        """Return the grid returned energy."""
        return self._grid_returned_energy_hour

    @property
    def grid_returned_energy_today(self):
        """Return the grid returned energy."""
        return self._grid_returned_energy_today

    @property
    def grid_returned_energy_month(self):
        """Return the grid returned energy."""
        return self._grid_returned_energy_month

    @property
    def grid_returned_energy_total(self):
        """Return the grid returned energy."""
        return self._grid_returned_energy_total

    @property
    def balance_neto_hour(self):
        """Return the grid returned energy."""
        return self._balance_neto_hour

    @property
    def balance_neto_today(self):
        """Return the grid returned energy."""
        return self._balance_neto_today

    @property
    def balance_neto_month(self):
        """Return the grid returned energy."""
        return self._balance_neto_month

    @property
    def balance_neto_total(self):
        """Return the grid returned energy."""
        return self._balance_neto_total

    async def register(self, sensor):
        """Register child sensor for update subscriptions."""
        self._sensors.add(sensor)

#   FroniusFetcher
#----------------------------------------------------------------------------------------------------------------------------------


class PowerflowData(FroniusFetcher):
    """Handle Fronius API object and limit updates."""

    def _build_url(self):
        """Build the URL for the requests."""
        url = _POWERFLOW_URL.format(self._ip_address)
        return url

    async def _update(self):
        """Get the latest data from inverter."""
        _LOGGER.debug("-->{}s {}(PowerflowData) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))
        self._data = (await self.fetch_data(self._build_url()))['Body']['Data']
        current_time = time.time()
        elapsed = int(round(current_time - self._latest_call))
        grid_energy_elapsed = self._latest_grid_power * elapsed
        house_energy_elapsed = self._latest_house_power * elapsed
        self._balance_neto_hour -= grid_energy_elapsed
        if self._latest_grid_power > 0:
            self._grid_energy_hour += grid_energy_elapsed
            self._grid_energy_today += grid_energy_elapsed
            self._grid_energy_month += grid_energy_elapsed
            self._grid_energy_total += grid_energy_elapsed
        else:
            self._grid_returned_energy_hour -= grid_energy_elapsed
            self._grid_returned_energy_today -= grid_energy_elapsed
            self._grid_returned_energy_month -= grid_energy_elapsed
            self._grid_returned_energy_total -= grid_energy_elapsed

        # house_power is a negative number
        if self._latest_house_power < 0:
            self._house_energy_hour -= house_energy_elapsed
            self._house_energy_today -= house_energy_elapsed
            self._house_energy_month -= house_energy_elapsed
            self._house_energy_total -= house_energy_elapsed

        if self._data:
            self._latest_grid_power = int(round(self._data['Site']['P_Grid']))
            self._latest_house_power = int(round(self._data['Site']['P_Load']))
            self._latest_call = current_time

        if dt_now().hour != self._hour:
            self._hour = dt_now().hour
            if self._grid_energy_hour > self._grid_returned_energy_hour:
                self._balance_neto_today += self._grid_returned_energy_hour
                self._balance_neto_month += self._grid_returned_energy_hour
                self._balance_neto_total += self._grid_returned_energy_hour
            else:
                self._balance_neto_today += self._grid_energy_hour
                self._balance_neto_month += self._grid_energy_hour
                self._balance_neto_total += self._grid_energy_hour

            self._balance_neto_hour = 0
            self._grid_energy_hour = 0
            self._house_energy_hour = 0
            self._grid_returned_energy_hour = 0
            if dt_now().day != self._day:
                self._day = dt_now().day
                self._balance_neto_today = 0
                self._grid_energy_today = 0
                self._house_energy_today = 0
                self._grid_returned_energy_today = 0

                if dt_now().month != self._month:
                    self._month = dt_now().month
                    self._balance_neto_month = 0
                    self._grid_energy_month = 0
                    self._house_energy_month = 0
                    self._grid_returned_energy_month = 0

        _LOGGER.debug("<--{}s {}(PowerflowData) ({}:{})".format(round(time.time() - start_time, 3), inspect.currentframe().f_code.co_name, os.path.basename(__file__), inspect.currentframe().f_lineno))

#   PowerflowData
#----------------------------------------------------------------------------------------------------------------------------------




#------------------------------------------------------  END OF DOCUMENT  ---------------------------------------------------------
