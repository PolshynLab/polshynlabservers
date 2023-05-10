import labrad
import numpy as np

cxn = labrad.connect()
reg = cxn.registry

reg.cd('Servers')
Servers_list = reg.dir()
print('A list of all Serial Servers')
print(Servers_list)

device = ['Mercury IPS Server', 'Mercury ITC Server', 'dac_adc','SIM900']
Num_Device = np.size(device)
print('The Serial Devices we look for')
print(device)

device_name = ['']*Num_Device
device_temp1 = ['']
device_temp2 = ['']
deviceID_temp = ['']

def get_deviceID(device_name):
    i = 0
    print('\n')
    print('Device ID and COM port of each device')
    for name in device:
        
        # Go to inner folder of each device
        reg.cd(name)
        reg.cd('Links')
        device_temp1 = reg.dir()
        device_temp2 = device_temp1[1]
        device_name[i] = device_temp2[0]
        deviceID_temp = reg.get(device_name[i])


        print('\n')
        print(name)
        print(device_name[i],  " COM port ",  deviceID_temp[1])

        reg.cd('..')
        reg.cd('..')

        i = i+1

get_deviceID(device_name)

i = 0
# for name in device:
#     print('\n')
#     print(name + ' COM port')
#     reg.cd(name)
#     reg.cd('Links')

#     deviceID_temp = reg.get(device_name[i])
#     print(deviceID_temp[1])

#     reg.cd('..')
#     reg.cd('..')
#     i = i + 1



