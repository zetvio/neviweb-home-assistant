# Home Assistant Neviweb and Sinope Custom Components

Here are two custom components to suport [Neviweb](https://neviweb.com/) in [Home Assistant](http://www.home-assistant.io). 
Neviweb is a platform created by Sinopé Technologies to interact with their smart devices like thermostats, light switches/dimmers and load controllers. It also supports some devices made by [Ouellet](http://www.ouellet.com/en-ca/products/thermostats-and-controls/neviweb%C2%AE-wireless-communication-controls.aspx).

## Supported Devices
Here is a list of currently supported devices. Basically, it's everything that can be added in Neviweb.
- Thermostats
  - Sinopé TH1120RF-3000 Line voltage thermostat
  - Sinopé TH1120RF-4000 Line voltage thermostat
  - Sinopé TH1121RF-3000 Thermostat for public areas
  - Sinopé TH1121RF-4000 Thermostat for public areas
  - Sinopé TH1300RF Floor heating thermostat
  - Sinopé TH1400RF Low voltage thermostat
  - Sinopé TH1500RF Double-pole thermostat
  - *Ouellet OTH2750-GT Line voltage thermostat
  - *Ouellet OTH3600-GA-GT Floor heating thermostat
- Lighting
  - Sinopé SW2500RF Light switch
  - Sinopé DM2500RF Dimmer 
- Specialized Control
  - Sinopé RM3200RF Load controller 40A
  - Sinopé RM3250RF Load controller 50A

*Not tested, but should be working well. Your feedback is appreciated if a device doesn't work.

## Prerequisite
You need to connect your devices to a GT125 web gateway and add them in your Neviweb portal before being able to interact with them within Home Assistant. Please refer to the instructions manual of your device or visit [Neviweb support](https://www.sinopetech.com/blog/support-cat/plateforme-nevi-web/).

There are two custom component giving you the choice to manage your devices via the neviweb portal or directly via your GT125 router:
- Neviweb custom component to manage your devices via neviweb portal
- Sinope custom component to manage your devices directly via your GT125 router

You need to install only one of them but both can be used at the same time on HA.

## Neviweb custom component to manage your device via Neviweb portal:
## Installation
1. Download the zip file of this repository using the top right, green download button.
1. Extract the zip file on your computer, then copy the entire `custom_components` folder inside your Home Assistant `config` directory (where you can find your `configuration.yaml` file).
1. Your config directory should look like this:

    ```
    config/
      configuration.yaml
      custom_components/
        neviweb/
          __init__.py
          light.py
          switch.py
          climate.py
      ...
    ```

## Configuration

To enable Neviweb management in your installation, add the following to your `configuration.yaml` file, then restart Home Assistant.

```yaml
# Example configuration.yaml entry
neviweb:
  username: '<your Neviweb username>'
  password: '<your Neviweb password>'
```

**Configuration options:**  

| key | required | default | description
| --- | --- | --- | ---
| **username** | yes |  | Your email address used to log in Neviweb.
| **password** | yes |  | Your Neviweb password.
| **network** | no | 1st network found | The name of the network you want to control.
| **scan_interval** | no | 900 | The number of seconds between access to Neviweb to update device state. Sinopé asked for a minimum of 5 minutes between polling now so you can reduce scan_interval to 300.

## Troubleshooting
If you get a stack trace related to a Neviweb component in your `home-assistant.log` file, you can file an issue in this repository.

You can also post in one of those threads to get help:
- https://community.home-assistant.io/t/sinope-line-voltage-thermostats/17157
- https://community.home-assistant.io/t/adding-support-for-sinope-light-switch-and-dimmer/38835

### Turning on Neviweb debug messages in `home-assistant.log` file

To have a maximum of information to help you, please provide a snippet of your `home-assistant.log` file. I've added some debug log messages that could help diagnose the problem.

Add thoses lines to your `configuration.yaml` file
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.neviweb: debug
   ```
This will set default log level to warning for all your components, except for Neviweb which will display more detailed messages.

## Sinope custom component to manage your devices via the GT125 router:
## Installation
1. Download the zip file of this repository using the top right, green download button.
1. Extract the zip file on your computer, then copy the entire `custom_components` folder inside your Home Assistant `config` directory (where you can find your `configuration.yaml` file).
1. Your config directory should look like this:

    ```
    config/
      configuration.yaml
      custom_components/
        sinope/
          __init__.py
          light.py
          switch.py
          climate.py
          device.py
          devices.json
      ...
    ```
## Configuration

To enable Sinope management in your installation, add the following to your `configuration.yaml` file, then restart Home Assistant.

```yaml
# Example configuration.yaml entry
sinope:
  server: '<Ip adress of your GT125>'
  id: '<ID written on the back of your GT125>' non space
  api_key: '<Api_key received on first manual connection with the GT125>' #run device.py for that
  dk_key: '<your Dark sky key>'
  my_city: '<the nearest city>' #needed to get sunrise and sunset hours for your location.
  scan_interval: 120 #you can go down to 60 if you want depending on how many devices you have to update. Default set to 180
  ```
## First run

To setup this custom_component, login to your Rpi and cd to the directory where you have copied the file.
- Edit the file device.py to add your GT125 IP address at the line 10.
```yaml
server = 192.168.x.x 
```
- Add your device ID, written on the back of your GT125, on line 14. (without space) You will need to write it the same way in your configuration.yaml file.

Execute the command: python3 device.py in console. This is required to get the Api_Key and the deviceID for each Sinopé devices connected to your GT125. On first run, device.py send a ping request to the GT125 and it will ask you to push de "WEB" button on the GT125. 
This will give you the Api Key that you need to write on line 12, 
```yaml
api_key = "xxxxxxxxxxxxxxxx" 
```
- make sure your GT125 use the port 4550, this is the one by default or change line 18 accordingly.
- once you get your Api_Key you will start to get the device_id for all devices connected to your GT125.  See devices discovery bellow.

You're ready to setup your Sinopé devices.

I've put lots of comment in the code so I think you will understand.

Main difference with Neviweb is that with the GT125 we don't have command to request all data and info 
from one device at once. We need to issue one data read request for each info or data we want. 
ex:
- open a connection
- login to the GT125
- send data read request for room temperature
- send data read request for setpoint temperature
- send data read request for mode (manual, auto, off, away)
- send data read request for heat level
- etc
- close connection and start over for next device.

This is the same for data write request but in that case we normally send one data like changing temperature or mode 
to one device. One exception is when we sent request to change mode to auto. We need to send correct time prior to send write request for auto mode.

For the data report request it is possible to send data to all device at once by using a specific deviceID = FFFFFFFF. 
It is used to send time, date, sunset and sunrise hour, outside temperature, set all device to away mode, etc, broadcasted to all device.

## Devices discovery
Look like the GT125 use a different deviceID then Neviweb. Once you have your Api_key written in device.py, you will need to run it to request deviceID for each devices on your network one by one. The program will wait for you to push on both button of your device to revceive the deviceID of that device. Then, it will ask for device data like name, type and connected watt load. To get the list of devices types just type "h" when asked for device type. This will display all known types and then ask for your device type. If you don't have all information just hit enter to leave those fields blank. It will be possible to add missing data later. All devices ID and data will be written in file devices.json. Once you have all your devices, hit "q" at the end to quit the program. Edit devices.json and add the name, type and wattage (for light devices) for each devices. Light connected watt load is not measured by the light devices but instead written in Neviweb on setup of light devices. We need to write it to devices.json (kind of Neviweb portal equivalent) to finish the devices setup. ex:

```yaml
["id", "name", "type", "watt"] <- do not edit this line
["00470100", " ", " ", " "] <- once discovered by device.py, add devices info between the " "
["2e320100", "Office heating", "10", " "] <- thermostat ex.
["5a2c0100", "Office light", "102", "60"] <- light ex.
["6a560100", "Outside timer", "120", " "] <- power switch ex.
["00470100", "Dimmer TV Room", "112", "110"] <- Dimmer ex.
```
For power switch devices, RM3250RF and RM3200RF, you need to push on the top blue ligth to get the deviceID.
Each time you will add a new device to your GT125 you will need to run that setup.

## Customization
Install Custom UI and add the following in your code:

Icons for heat level: create folder www in the root folder .homeassistant/www
copy the six icons there. You can find them under local/www
feel free to improve my icons and let me know. (See icon_view2.png)

For each thermostat add this code in `customize.yaml`
```yaml
climate.neviweb_climate_thermostat_name:
  templates:
    entity_picture: >
      if (attributes.heat_level < 1) return '/local/heat-0.png';
      if (attributes.heat_level < 21) return '/local/heat-1.png';
      if (attributes.heat_level < 41) return '/local/heat-2.png';
      if (attributes.heat_level < 61) return '/local/heat-3.png';
      if (attributes.heat_level < 81) return '/local/heat-4.png';
      return '/local/heat-5.png';
 ```  
 In `configuration.yaml` add this
```yaml
customize: !include customize.yaml
``` 

## Current Limitations
- Home Assistant doesn't support operation mode selection for light and switch entities. So you won't see any dropdown list in the UI where you can switch between Auto and Manual mode. You can only see the current mode in the attributes. TODO: register a new service to change operation_mode and another one to set away mode.

- If you're looking for the away mode in the Lovelace 'thermostat' card, you need to click on the three dots button on the top right corner of the card. That will pop a window were you'll find the away mode switch at the bottom.

## TO DO
- Document each available services for every platforms + available attributes.
- Explore how to automatically setup sensors in HA that will report the states of a specific device attribute (i.e. the wattage of a switch device)

For Sinope custom component:
- Leave socket open to listen for events from devices state changes and answers from our data request. For now I open, send request, get result then close socket.
- Detect events from light dimer and switch so we can receive state changes from the GT125 without polling the devices (faster).
- Send time, date, sunset, sunrise once a day to each devices. Need to find out how to do that once a day at specific time.
- Send outside temperature to thermostat once per hour to have it displayed on the second display line. Maybe could be done from automation but would prefer to do it inside Sinope directly.
- Improve logging and debug.

## Contributing
You see something wrong or something that could be improved? Don't hesitate to fork me and send me pull requests.
