# Copyright []
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
### BEGIN NODE INFO
[info]
name = Stepper Motor Controllers
version = 1.0
description = ACBOX control

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

import platform
global serial_server_name
serial_server_name = (platform.node() + '_serial_server').replace('-','_').lower()

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
from collections import deque
import time

TIMEOUT = Value(5,'s')
BAUD    = 115200
BYTESIZE = 8
STOPBITS = 1
PARITY = 0

class ITCWrapper(DeviceWrapper):

    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device."""
        print('connecting to "%s" on port "%s"...' % (server.name, port), end=' ')
        self.server = server
        self.ctx = server.context()
        self.port = port
        p = self.packet()
        p.open(port)
        p.baudrate(BAUD)
        p.bytesize(BYTESIZE)
        p.stopbits(STOPBITS)
        p.setParity = PARITY
        p.read()  # clear out the read buffer
        p.timeout(TIMEOUT)
        #p.timeout(None)
        print(" CONNECTED ")
        yield p.send()

    def packet(self):
        """Create a packet in our private context"""
        return self.server.packet(context=self.ctx)

    def shutdown(self):
        """Disconnect from the serial port when we shut down"""
        return self.packet().close().send()

    @inlineCallbacks
    def write(self, code):
        """Write a data value to the device"""
        yield self.packet().write(code).send()

    @inlineCallbacks
    def read(self):
        """Read a response line from the device"""
        p=self.packet()
        p.read_line()
        ans=yield p.send()
        returnValue(ans.read_line)

    @inlineCallbacks
    def query(self, code):
        """ Write, then read. """
        p = self.packet()
        p.write_line(code)
        p.read_line()
        ans = yield p.send()
        returnValue(ans.read_line)


class ITCServer(DeviceServer):
    name             = 'Mercury ITC Server'
    deviceName       = 'Mercury ITC Temperature Control'
    deviceWrapper    = ITCWrapper

    @inlineCallbacks
    def initServer(self):
        print('loading config info...', end=' ')
        self.reg = self.client.registry()
        yield self.loadConfigInfo()
        print('done.')
        print(self.serialLinks)
        yield DeviceServer.initServer(self)
        self.stack  = deque([])

    @inlineCallbacks
    def loadConfigInfo(self):
        reg = self.reg
        yield reg.cd(['', 'Servers', 'Mercury ITC Server', 'Links'], True)
        dirs, keys = yield reg.dir()
        p = reg.packet()
        print("Created packet")
        print("printing all the keys",keys)
        for k in keys:
            print("k=",k)
            p.get(k, key=k)
        ans = yield p.send()
        #print("ans=",ans)
        self.serialLinks = dict((k, ans[k]) for k in keys)

    @inlineCallbacks
    def findDevices(self):
        devs = []
        for name, (serServer, port) in list(self.serialLinks.items()):
            if serServer not in self.client.servers:
                print(serServer)
                #print(self.client.servers)
                continue
            server = self.client[serServer]
            ports = yield server.list_serial_ports()
            if port not in ports:
                continue
            devName = '%s - %s' % (serServer, port)
            devs += [(devName, (server, port))]
        returnValue(devs)

    @setting(506, returns='s')
    def iden(self,c):
        """Identifies the stepper controller device."""
        dev=self.selectedDevice(c)
        yield dev.write("*IDN?\n\r")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(507, returns='s')
    def system(self,c):
        dev=self.selectedDevice(c)
        print("Writting X")
        yield dev.write("READ:SYS:CAT\n")
        ans = yield dev.read()
        returnValue(ans)
        
    
    #temperature control commands
    
    @setting(525, returns='s')
    def insert_temperature_read(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:MB1.T1:TEMP:SIG:TEMP"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)
        
    @setting(526, returns='s')
    def probe_temperature_read(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB8.T1:TEMP:SIG:TEMP"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)
        
    @setting(527, returns='s')
    def read_probe_temperature_setpoint(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:TSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)
        
    @setting(528, target = 'v', returns='s')
    def set_probe_temperature_setpoint(self, c, target):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:TSET:"+str(target)+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
          
    @setting(529, target = 'v', returns='s')
    def set_probe_temperature_ramp_rate(self, c, target):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:RSET:"+str(target)+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(530, returns='s')
    def read_probe_temperature_ramp_rate(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:RSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)

    @setting(531, returns='s')
    def ramp_the_probe(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:RENA:ON\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(532, returns = 's')
    def stop_ramping_the_probe(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:RENA:OFF\n")
        ans = yield dev.read()
        returnValue(ans)
          
    @setting(533, target = 'v', returns='s')
    def set_insert_temperature_ramp_rate(self, c, target):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RSET:"+str(target)+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(534, returns='s')
    def read_insert_temperature_ramp_rate(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:MB1.T1:TEMP:LOOP:RSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)

    @setting(535, returns='s')
    def ramp_the_insert(self,c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RENA:ON\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(536, returns = 's')
    def stop_ramping_the_insert(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RENA:OFF\n")
        ans = yield dev.read()
        returnValue(ans)
    
#pressure control commands
    @setting(537, returns = 's')
    def read_pressure(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB5.P1:PRES:SIG:PRES"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)
        
    @setting(538, target = 'v', returns = 's')    
    def set_pressure_setpoint(self, c, target):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB5.P1:PRES:LOOP:TSET:"+str(target)+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(539, returns = 's')
    def read_pressure_setpoint(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB5.P1:PRES:SIG:PRES"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(ans)
        
    @setting(540, returns = 's')
    def read_pressure_sweep_status(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB5.P1:PRES:LOOP:SWMD"+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(541, returns = 's')
    def sweep_the_pressure(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB5.P1:PRES:LOOP:SWMD:ON"+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(542, returns = 's')
    def stop_sweeping_the_pressure(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:DB5.P1:PRES:SIG:PRES"+"\n")
        ans = yield dev.read()
        returnValue(ans)


#enable/disable ramp mode
    @setting(543, returns = 's')
    def enable_ramp_mode(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RENA:ON"+"\n")
        ans = yield dev.read()
        returnValue(ans)

    @setting(544, returns = 's')
    def disable_ramp_mode(self, c):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RENA:OFF"+"\n")
        ans = yield dev.read()
        returnValue(ans)
        
        
    @setting(545, target = 'v', returns='s')
    def set_insert_temperature_setpoint(self, c, target):
        dev=self.selectedDevice(c)
        yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:TSET:"+str(target)+"\n")
        ans = yield dev.read()
        returnValue(ans)

    
    
__server__ = ITCServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
