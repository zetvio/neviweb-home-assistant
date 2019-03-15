import struct
import binascii
import socket
import sys
import crc8
from datetime import datetime
import pytz

class SinopeError(Exception):
    """Generic error of Sinope unit."""
    pass

### data that will come from HA
SERVER = '192.168.2.163' #ip address of the GT125
#write key here once you get it with the ping request
Api_Key = None
# this is the ID printed on your GT125 but you need to write it reversly.
# ex. ID: 0123 4567 89AB CDEF => EFCDAB8967452301
Api_ID = "xxxxxxxxxxxxxxxx" 
###

PORT = 4550
#sequential number to identify the current request. Could be any unique number that is different at each request
# could we use timestamp value ?
seq_num = 12345678 
seq = 0

# command type
data_read_command = "4002"
data_report_command = "4202"
data_write_command = "4402"

# device identification
all_unit = "FFFFFFFF" #for data_report_command only
device_id = "2e320100" # receive from GT125 device link report. Only for test purpose. Will be sent by HA

#thermostat data read
data_heat_level = "20020000" #0 to 100%
data_mode = "11020000" 
data_temperature = "03020000" #room temperature
data_setpoint = "08020000"
data_away = "00070000"

# thermostat data report
data_outdoor_temperature = "04020000" #to show on thermostat, must be sent at least every hour
data_time = "00060000"
data_date = "01060000"

# thermostat data write
data_early_start = "60080000"  #0=disabled, 1=enabled
manual_mode = "0102" #include the size bytes
auto_mode = "0103" #include the size bytes
off_mode = "0100" #include the size bytes

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

def set_time():
    tz_NY = pytz.timezone('America/New_York')
    now = datetime.now(tz_NY)
    s = bytearray(struct.pack('<i', int(now.strftime("%S")))[:1]).hex() #second converted to bytes
    m = bytearray(struct.pack('<i', int(now.strftime("%M")))[:1]).hex() #minutes converted to bytes
    h = bytearray(struct.pack('<i', int(now.strftime("%H")))[:1]).hex() #hours converted to bytes
    time = '03'+s+m+h #xxssmmhh  24hr, 16:09:00 pm, xx = lenght of data time = 03
    return time

def get_heat_level(data):
    sequence = data[12:]
    laseq = sequence[:8]
    print('sequence = '+laseq)
    dev = data[26:]
    deviceID = dev[:8]
    print('device ID = '+deviceID)
    tc1 = data[46:]
    tc2 = tc1[:2]
    return int(float.fromhex(tc2))
  
def set_temperature(temp_celcius): #temperature is always in celcius sent as 0.01oC unit. 21.5oC sent as 2150
    temp = int(temp_celcius*100)
    return "02"+bytearray(struct.pack('<i', temp)[:2]).hex()
  
def get_temperature(data):
    sequence = data[12:]
    laseq = sequence[:8]
    print('sequence = '+laseq)
    dev = data[26:]
    deviceID = dev[:8]
    print('device ID = '+deviceID)
    tc1 = data[46:]
    tc2 = tc1[:2]
    tc3 = data[48:]
    tc4 = tc3[:2]
    latemp = tc4+tc2
    return float.fromhex(latemp)*0.01  
  
def send_request(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      sock.sendall(login_request())
      if binascii.hexlify(sock.recv(1024)) == b'55000c001101000000030000032000009c': #login ok
         print('sending data request')
         sock.sendall(data)
         reply = sock.recv(1024)
         print('answer = "%s"' % binascii.hexlify(reply))
         if crc_check(reply):  # receive acknoledge, check status and if we will receive more data
             seq_num = binascii.hexlify(reply)[12:20] #sequence id to link response to the correct request
             status = binascii.hexlify(reply)[20:22]
             more = binascii.hexlify(reply)[24:26] #check if we will receive other data
             if status == b'00': # request status = ok for read and write, we go on (read=00, report=01, write=00)
                 if more == b'01': #GT125 is sending another data
                     datarec = sock.recv(1024)           
                     return datarec
             elif status == b'01': #status ok for data report
                 return reply
             else:       
                 print('Error data sent')
         return reply   
    finally:
      sock.close()

def get_device_id():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      sock.sendall(login_request())
      if binascii.hexlify(sock.recv(1024)) == b'55000c001101000000030000032000009c': #login ok
        print('Please push the two buttons on the device you want to identify')
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
      
def split_received_data(data): 
    return

def retreive_key(data):
    binary = data[18:]
    key = binary[:16]
    return key
  
def ping_request():
    ping_data = "550002001200"
    ping_crc = bytes.fromhex(crc_count(bytes.fromhex(ping_data)))
    return bytes.fromhex(ping_data)+ping_crc
      
def key_request(serial):
    key_data = "55000A000A01"+serial
    key_crc = bytes.fromhex(crc_count(bytes.fromhex(key_data)))
    return bytes.fromhex(key_data)+key_crc
  
def login_request():
    login_data = "550012001001"+Api_ID+Api_Key
    login_crc = bytes.fromhex(crc_count(bytes.fromhex(login_data)))
    return bytes.fromhex(login_data)+login_crc
  
def get_seq(seq):
    if seq == 0:
      seq = seq_num
    seq += 1  
    return str(seq)  
  
def count_data(data):
    size = int(len(data)/2)
    return bytearray(struct.pack('<i', size)[:2]).hex() 
  
def data_read_request(command,unit_id,data_app): # 21310500 ou FFFFFFFF
    head = "5500"
    data_command = command
    data_seq = get_seq(seq)
    data_type = "00"
    data_res = "000000000000"
    data_dest_id = unit_id
    app_data_size = "04"
    size = count_data(command+data_seq+data_type+data_res+unit_id+app_data_size+data_app)
    data_frame = head+size+command+data_seq+data_type+data_res+unit_id+app_data_size+data_app
    print('data frame = "%s"' % data_frame)
    read_crc = bytes.fromhex(crc_count(bytes.fromhex(data_frame)))
    return bytes.fromhex(data_frame)+read_crc
  
def data_report_request(command,unit_id,data_app,data): # data = size+time or size+temperature
    head = "5500"
    data_command = command
    data_seq = get_seq(seq)
    data_type = "00"
    data_res = "000000000000"
    data_dest_id = unit_id
    app_data_size = count_data(data_app+data)
    size = count_data(command+data_seq+data_type+data_res+unit_id+app_data_size+data_app+data)
    data_frame = head+size+command+data_seq+data_type+data_res+unit_id+app_data_size+data_app+data
    print('data frame = "%s"' % data_frame)
    read_crc = bytes.fromhex(crc_count(bytes.fromhex(data_frame)))
    return bytes.fromhex(data_frame)+read_crc
  
def data_write_request(command,unit_id,data_app,data): # data = size+data to send
    head = "5500"
    data_command = command
    data_seq = get_seq(seq)
    data_type = "00"
    data_res = "000000000000"
    data_dest_id = unit_id
    app_data_size = count_data(data_app+data)
    size = count_data(command+data_seq+data_type+data_res+unit_id+app_data_size+data_app+data)
    data_frame = head+size+command+data_seq+data_type+data_res+unit_id+app_data_size+data_app+data
    print('data frame = "%s"' % data_frame)
    read_crc = bytes.fromhex(crc_count(bytes.fromhex(data_frame)))
    return bytes.fromhex(data_frame)+read_crc
  
# send ping to gt125      
if binascii.hexlify(send_ping_request(ping_request())) == b'55000200130021':
    if Api_Key == None:
      print("ok we can send the api_key request\n")
      print("push the GT125 web button")
      print('Api key : ',retreive_key(binascii.hexlify(send_request(key_request(Api_ID)))))
      print('Copy this value in the Api_Key, replacing the _None_ value')

print('Sending app data request')
### example data read request uncoment the one you want to test

# read thermostat heat level
#print(get_heat_level(bytearray(send_request(data_read_request(data_read_command,device_id,data_heat_level))).hex()))

# read room temperature
#print(get_temperature(bytearray(send_request(data_read_request(data_read_command,device_id,data_temperature))).hex()))

### example data report request sent to all devices
# broadcast local time
#print(binascii.hexlify(send_request(data_report_request(data_report_command,all_unit,data_time,set_time()))))

### example data write request
# set thermostat to manual mode
#print(binascii.hexlify(send_request(data_write_request(data_write_command,device_id,data_mode,manual_mode))))
### send setpoint temperature at 21.5oC
#print(binascii.hexlify(send_request(data_write_request(data_write_command,device_id,data_setpoint,set_temperature(21.50)))))

# finding device ID, one by one
#print(get_device_id())
#print('repeat program for each device')
