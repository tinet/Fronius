# Fronius custom component for Home Assistant
This component simplifies the integration of a Fronius inverter (Smart Meter is mandatory):

The API used for retrieving the Fronius values is lightweight, so you can called it at most each 2 seconds (4 seconds recommended)

Creates 24 individual sensors:
```
fronius_pv_power
fronius_grid_power
fronius_house_power

fronius_self_sufficiency
fronius_self_consumption

fronius_pv_energy_today
fronius_pv_energy_year
fronius_pv_energy_total
 
fronius_grid_energy_hour
fronius_grid_energy_today
fronius_grid_energy_month
fronius_grid_energy_total
 
fronius_house_energy_hour
fronius_house_energy_today
fronius_house_energy_month
fronius_house_energy_total
 
fronius_grid_returned_energy_hour
fronius_grid_returned_energy_today
fronius_grid_returned_energy_month
fronius_grid_returned_energy_total

fronius_balance_neto_hour
fronius_balance_neto_today
fronius_balance_neto_month
fronius_balance-neto_total
```

Create 1 sensor for each inverter in the system showing the inverter's power production:
* fronius_inverter1_power
* ...
* fronius_inverterN_power

### Fronius API used
The URL called is ``http://<fronius ip>/solar_api/v1/GetPowerFlowRealtimeData.fcgi``
```
{
   "Body" : {
      "Data" : {
         "Inverters" : {
            "1" : {
               "DT" : 75,
               "E_Day" : 794.4000244140625,
               "E_Total" : 2014358.125,
               "E_Year" : 268438.71875,
               "P" : 1200
            },
            "2" : {
               "DT" : 75,
               "E_Day" : 303.20001220703125,
               "E_Total" : 2127122.25,
               "E_Year" : 248875.5,
               "P" : 350
            }
         },
         "Site" : {
            "E_Day" : 1097.6000366210938,
            "E_Total" : 4141480.375,
            "E_Year" : 517314.21875,
            "Meter_Location" : "grid",
            "Mode" : "meter",
            "P_Akku" : null,
            "P_Grid" : -1005.12,
            "P_Load" : -544.88,
            "P_PV" : 1550,
            "rel_Autonomy" : 100,
            "rel_SelfConsumption" : 35.15354838709
         },
         "Version" : "12"
      }
   },
   "Head" : {
      "RequestArguments" : {},
      "Status" : {
         "Code" : 0,
         "Reason" : "",
         "UserMessage" : ""
      },
      "Timestamp" : "2020-04-13T18:46:49+01:00"
   }
}
```

### Installation
Copy the ``fronius_basic`` folder to your custom_components directory of Home Assistant.

E.g.:
```
../config/custom_components/fronius_basic/__init__.py
../config/custom_components/fronius_basic/manifest.json
../config/custom_components/fronius_basic/sensor.py
```

### Configuration
```
# configuration.yaml entry:
sensor:
  - platform: fronius_basic
    ip_address: <fronius ip>
    scan_interval: <seconds>
```    
### Configuration Example
```
# configuration.yaml entry:
sensor:
  - platform: fronius_basic
    ip_address: 192.168.1.6
    scan_interval: 4
```    
