The file pysinope.py is a preliminary implementation of a direct connection to the GT125.
Presently it work manualy via a ssh login to my Rpi hasbian where HA is installed.
 
Copy the file pysinope.py to your /home/homeassistant/.homeassistant/custom_components/neviweb or 
any directory under custom_component.
To run it just login to your Rpi and cd to the directory where you have copied the pysinope.py
The command is: python3 pysinope.py

Prior to test there are some prerequisit to do:

- You need to install CRC8 module from PyPI with the command:
pip install crc8 (in my case it was pip3 install crc8)

- You will need to edit the file to add your GT125 ID that is writen on the back of the router.
Because all command are sent in binary with following spec:

Byte order:    LSB first 
Bit order:     msb first 
Initial value: 0x00 
Final XOR:     0x00 (none)
CRC 8

you will need to enter the ID in a specific maner: 
ex: if ID = 0123 4567 89AB CDEF then write EFCDAB8967452301 at line 20 for Api_ID

- You must add your GT125 IP address on line 15
SERVER = 192.168.x.x 

- make sure your GT125 use the port 4550

I've put lots of comment in the code so I think you will understand. At the end of the file there are many lines that you can 
uncomment to test the different command.

Main difference with neviweb is that with the GT125 we don't have command to request all data and info 
from a device at once. We need to issue on data read request for each info we want. 
- open connection
- login to the GT125
- send data read request for room temperature
- send data read request for setpoint temperature
- send data read request for mode (manual, auto, off, away)
- send data read request for heat level
- etc
- close connection and start over for next device.

This is the same for data write request but in that case we normally send one data like changing temperature or mode 
to one device.

For the data report request it is possible to send data to all device at once by using a deviceID = FFFFFFFF. 
It is used to send time, date, outside temperature, set to away mode, etc to all device.

Look like the GT125 use a different deviceID then Neviweb.You will find at the bottom of the file a line that you can 
uncomment to receive your deviceID from the GT125. You need to run the program once for each device. The program will wait for 
you to push on both button of your device to revceive the deviceID. Once you get one, write it on line 36. You need one to start
playing with.

I've added command for the thermostat first because I think it is what most people are waiting for. I can add all command for the 
light switch and dimmer and the power controler.

Test it and let me know. Any help is welcome. There is still lot of work to do to use it in HA.
