# you need to install crc8 module -> pip3 install crc8
import binascii
import socket
import sys
import crc8
import json
import io

### data that will come from HA
SERVER = 'XXX.XXX.XXX.XXX' #ip address of the GT125
#write key here once you get it with the ping request
Api_Key = None # "api_key"
# this is the ID printed on your GT125 but you need to write it reversely.
# ex. ID: 0123 4567 89AB CDEF => EFCDAB8967452301
Api_ID = "xxxxxxxxxxxxxxxx" 
###

PORT = 4550

def crc_count(bufer):
        hash = crc8.crc8()
        hash.update(bufer)
        return hash.hexdigest()

def crc_check(bufer):
        hash = crc8.crc8()
        hash.update(bufer)
        if(hash.hexdigest() == "00"):
          return "00"
        return None

def get_device_id():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      sock.sendall(login_request())
      if binascii.hexlify(sock.recv(1024)) == b'55000c001101000000030000032000009c': #login ok
        print('Please push the two button on the device you want to identify')
        datarec = sock.recv(1024)
        id = bytearray(datarec).hex()[14:22]
      return id
    finally:
      sock.close()

def send_ping_request(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      sock.sendall(data)
      reply = sock.recv(1024)
      if crc_check(reply):
          return reply
    finally:
      sock.close()

def ping_request():
    ping_data = "550002001200"
    ping_crc = bytes.fromhex(crc_count(bytes.fromhex(ping_data)))
    return bytes.fromhex(ping_data)+ping_crc
  
def key_request(serial):
    key_data = "55000A000A01"+serial
    key_crc = bytes.fromhex(crc_count(bytes.fromhex(key_data)))
    return bytes.fromhex(key_data)+key_crc

def retreive_key(data):
    binary = data[18:]
    key = binary[:16]
    return key

def login_request():
    login_data = "550012001001"+Api_ID+Api_Key
    login_crc = bytes.fromhex(crc_count(bytes.fromhex(login_data)))
    return bytes.fromhex(login_data)+login_crc

def send_key_request(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      print('Sending key request...')
      sock.sendall(data)
      reply = sock.recv(1024)
      return reply    
    finally:
      sock.close()

# send ping to GT125      
if binascii.hexlify(send_ping_request(ping_request())) == b'55000200130021':
    if Api_Key == None:
      print("ok we can send the api_key request\n")
      print("push the GT125 <web> button")
      print('Api key : ',retreive_key(binascii.hexlify(send_key_request(key_request(Api_ID)))))
      print("Copy the value between the b'...' in the Api_Key, line 12, replacing the <None> value")
      print('and copy it to your sinope section in your configuration.yaml file, Api_Key: ')
    else:
      # finding device ID, one by one
      dev = get_device_id()
      # setup data line
      data = '["'+dev+'", " ", " ", " "]'
      # write data to file
      with io.open('devices.json', 'a', encoding='utf8') as outfile:
          outfile.write('\n')
          outfile.write(data)
      outfile.close()
      print('repeat program for each device')
      print('when finished, edit file devices.json to add more information about your devices name and type')
      print('Device type are listed in climate.py, light.py and switch.py')
