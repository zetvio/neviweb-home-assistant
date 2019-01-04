# Home Assistant Sinopé Custom Components

Here are my custom components for Sinopé thermostats, light, dimmer and power switch in Home Assistant. (http://www.home-assistant.io)

## Installation
Copy the sinope_climate.py component to your custom_components/climate directory.

Configure it then restart HA.

## Upgrade

I've changed the name of the thermostat component from sinope.py to sinope_climate.py for better uniformity between all sinope components. If you update from previous version you should adjust the name of your thermostats in your `groups.yaml` and `automations.yaml` or the thermostats won't be visible in HA.

## Configuration

To enable your Sinopé thermostats management in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
climate:
  - platform: sinope_climate
    username: '<your e-mail-adress>'
    password: '<your Neviweb password>'
    gateway: '<your gateway name>'
    scan_interval: 900 #to limit access to neviwed every 15 minutes. Requested by Sinope. They will upgrade there neviweb to allow more frequent request.  
```

To enable your Sinopé lights/dimmers in your installation, add the following to your `configuration.yaml` file:
```yaml
# Example configuration.yaml entry
light:
  - platform: sinope_light
    username: '<your e-mail-adress>'
    password: '<your Neviweb password>'
    gateway: '<your gateway name>'
    scan_interval: 900 #to limit access to neviwed every 15 minutes
  - platform: sinope_dimmer
    username: '<your e-mail-adress>'
    password: '<your Neviweb password>'
    gateway: '<your gateway name>'
    scan_interval: 900 #to limit access to neviwed every 15 minutes  
```
To enable your Sinopé power switch in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
switch:
  - platform: sinope-switch
    username: '<your e-mail-adress>'
    password: '<your Neviweb password>'
    gateway: '<your gateway name>'
    scan_interval: 900 #to limit access to neviwed every 15 minutes  
```

Configuration variables:

- **username** (*Required*): The email address that you use for Sinopé Neviweb.
- **password** (*Required*): The password that you use for Sinopé Neviweb.
- **gateway** (*Required*): The name of the network you wan't to control.
