#Fronius custom component for Home Assistant
This component simplifies the integration of a Fronius inverter (Smart Meter is mandatory):

The API used for retrieving the Fronius values is lightweight, so you can called it each second

Creates 5 individual sensors:
	- fronius_solar
	- fronius_energy_today
	- fronius_house_load
	- fronius_grid_injection
	- fronius_self_consumption

Create 1 sensor for each inverter in the system showing the inverter's power production:
	- fronius_inverter_1
            ...
	- fronius_inverter_n

URL's Utilised
The URL called is http://<IP Fronius>/solar_api/v1/GetPowerFlowRealtimeData.fcgi

Installation
Copy the fronius_basic folder in the custom_components directory into your own custom_components directory in your config directory of Home Assistant.

E.g.:
../config/custom_components/fronius_basic/__init__.py
../config/custom_components/fronius_basic/manifest.json
../config/custom_components/fronius_basic/sensor.py

Configuration
# configuration.yaml entry:
sensor:
  - platform: fronius_basic
    ip_address: <Fronius IP>
    name: 'Fronius'
    scan_interval: 1
