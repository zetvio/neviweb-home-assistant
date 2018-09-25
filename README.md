# Home Assistant Sinopé Custom Components

Here are my custom components for Sinopé thermostats in Home Assistant. (http://www.home-assistant.io)

## Installation
Copy the sinope.py component to your custom component climate directory.

Configure it then restart HA.

## Configuration

To enable your Sinopé thermostats management in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
climate:
  - platform: sinope
    username: '<your e-mail-adress>'
    password: '<your Neviweb password>'
    gateway: '<your gateway name>'
```

To enable your Sinopé thermostats lights/dimmers in your installation, add the following to your `configuration.yaml` file:
```yaml
# Example configuration.yaml entry
light:
  - platform: sinope
    username: '<your e-mail-adress>'
    password: '<your Neviweb password>'
    gateway: '<your gateway name>'
    scan_interval: 900 #to limit access to neviwed every 15 minutes
```

Configuration variables:

- **username** (*Required*): The email address that you use for Sinopé Neviweb.
- **password** (*Required*): The password that you use for Sinopé Neviweb.
- **gateway** (*Required*): The name of the network you wan't to control.
