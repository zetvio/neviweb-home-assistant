# Home Assistant Sinopé Custom Component with direct connection to your GT125

The file pysinope.py is a preliminary implementation of a direct connection to the GT125.
Presently it work manualy via a ssh login to my Rpi hassbian where HA is installed.

Since the direct connection is working we will start to implement a separate custom_component to 
prevent interfering with the more stable neviweb custom_component.

## Supported Devices

Same as neviweb custom_component.

## Prerequisite

- You need to install CRC8 module from PyPI with the command:
pip install crc8 (in my case it was pip3 install crc8)

## Installation

Create a directory named sinope under custom_component in your HA setup.

Copy the files in the sinope directory to your /home/homeassistant/.homeassistant/custom_components/sinope directory.

Once ready you will need to add entry for sinope in your configuration.yaml like this:

```yaml
# Example configuration.yaml entry
sinope:
  server: '<Ip adress of your GT125>'
  Api_ID: '<ID written on the back of your GT125>'
  Api_Key: '<Api_key received on first connection with the GT125>'
```
## First run

To setup this custom_component, login to your Rpi and cd to the directory where you have copied the file.
- Edit the file setup.py to add your GT125 IP address at the line 8.
- Add your device Api_ID, written on the back of your GT125, on line 13. (see how below) 

Execute the command: python3 setup.py. This is required to get the Api_Key and the deviceID for each Sinopé devices connected to your GT125. On first run, setup.py send a ping request to the GT125 and it will ask you to push de WEB button on the GT125. 
This will give you the Api Key that you need to write on line 10, 
```yaml
Api_Key = "xxxxxxxxxxxxxxxx" 
```
- You will need to edit the file setup.py to add your GT125 ID that is writen on the back of the router.
Because all command are sent in binary with following spec:

- Byte order:    LSB first 
- Bit order:     msb first 
- Initial value: 0x00 
- Final XOR:     0x00 (none)
- CRC 8

Enter the GT125 ID, written on the back, in a specific maner: 
ex: if ID = 0123 4567 89AB CDEF then write EFCDAB8967452301 at line 13 for Api_ID = xxxx (will be changed later)

- You must add your GT125 IP address on line 8.
```yaml
SERVER = 192.168.x.x 
```
- make sure your GT125 use the port 4550, this is the one by default.

I've put lots of comment in the code so I think you will understand.

Main difference with Neviweb is that with the GT125 we don't have command to request all data and info 
from one device at once. We need to issue on data read request for each info or data we want. 
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

Look like the GT125 use a different deviceID then Neviweb. You will need to use setup.py many time to request deviceID for each devices on your network one by one. You need to do this once. The program will wait for you to push on both button of your device to revceive the deviceID of that device. Once you get one, write it on line 39 (device_id = "XXXXXXXX") of the file pysinope.py. You need one to start playing with. 

I've added command for the thermostat first because I think it is what most people are waiting for. I will add all command for the light switch, dimmer and power controler.

For now there is a lot of print() command in the code. It's to help debug in console mode. Will be removed when connected to HA.

Test it and let me know. Any help is welcome. There is still lot of work to do to use it in HA.
