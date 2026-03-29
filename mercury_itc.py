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

# Updated 12/11/2023 Gregory Polshyn
# Updated 4/13/2024 Gregory Polshyn

"""
### BEGIN NODE INFO
[info]
name = Mercury ITC
version = 1.2
description = Oxford Temperature Controller 

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
    name             = 'Mercury ITC'
    deviceName       = 'Mercury ITC'
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
        yield reg.cd(['', 'Servers', 'Mercury ITC', 'Links'], True)
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
        
    @setting(525, 'VTI temperature', returns='v')
    def vti_temperature(self, c):
        """Query the value of the vti temperature

        Returns:
            (Value[K]): VTI temperature.
        """
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:MB1.T1:TEMP:SIG:TEMP"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))
        
    @setting(526, 'Probe temperature', returns='v')
    def probe_temperature(self, c):
        """Query the value of the probe temperature

        Returns:
            (Value[K]): Probe temperature.
        """
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB8.T1:TEMP:SIG:TEMP"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))
        
    @setting(527, 'Probe temperature setpoint', setpoint=['','v'], returns='v')
    def probe_temperature_setpoint(self, c, setpoint=None):  # working on this one
        """Set or get the probe temperature setpoint.

        Args:
            setpoint (Value[K]): Probe temperature setpoint. If not included, then we
                query the existing probe temperature setpoint.

        Returns:
            (Value[K]): Probe temperature setpoint.
        """
        dev = self.selectedDevice(c)
        if setpoint is not None:
            yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:TSET:"+str(setpoint)+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:TSET"+"\n")
        # ans = yield dev.query("READ:DEV:DB8.T1:TEMP:LOOP:TSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))
          
    @setting(529, 'Probe temperature ramp rate', ramp_rate = 'v', returns='v') 
    def probe_temperature_ramp_rate(self, c, ramp_rate=None):
        """Set or get the probe temperature ramp rate.

        Args:
            ramp_rate (Value[K/min]): Probe temperature ramp rate. If not included, then we
                query the existing probe temperature ramp rate.

        Returns:
            (Value[K/min]): Probe temperature ramp rate.
        """
        dev = self.selectedDevice(c)
        if ramp_rate is not None:
            yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:RSET:"+str(ramp_rate)+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:RSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-3]
        returnValue(float(ans))
    
    @setting(531, 'Ramp probe temperature setpoint', ramping = 'b', returns='b')
    def ramp_probe_temperature_setpoint(self,c, ramping=None):
        """Set or get ramping mode(ON/OFF) of the probe temperature setpoint.

        Args:
            ramping (True/False): Probe temperature setpoint is ON (TRUE) or OFF (FALSE). If not included, then we
                query the existing state of the ramping.

        Returns:
            (Boolean): Probe temperature setpoint is ON (TRUE) or OFF (FALSE).
        """
        dev=self.selectedDevice(c)
        if ramping is not None:
            if ramping is True:
                state = "ON"
            else:
                state = "OFF"
            yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:RENA:"+state+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:RENA\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        if ans=="ON":
            reply=True
        elif ans=="OFF":
            reply=False
        else:
            reply=None
        returnValue(reply)
        
    @setting(532, 'Probe temperature P', returns='v')  # doesn't work
    def probe_temperature_P(self,c, p=None):
        dev=self.selectedDevice(c)
        if p is not None:            
            yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:P:"+srt(p)+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:P\n")
        ans = yield dev.read()
        returnValue(ans)
        
    @setting(533, 'VTI temperature ramp rate', ramp_rate = 'v', returns='v')
    def vti_temperature_ramp_rate(self, c, ramp_rate=None):
        """Set or get the VTI temperature ramp rate.

        Args:
            ramp_rate (Value[K/min]): VTI temperature ramp rate. If not included, then we
                query the existing VTI temperature ramp rate.

        Returns:
            (Value[K/min]): VTI temperature ramp rate.
        """
        dev=self.selectedDevice(c)
        if ramp_rate is not None:
            yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RSET:"+str(ramp_rate)+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:MB1.T1:TEMP:LOOP:RSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-3]
        returnValue(float(ans))
        
    @setting(535, 'Ramp VTI temperature setpoint', ramping = 'b', returns='b')
    def ramp_vti_temperature_setpoint(self,c, ramping=None):
        """Set or get ramping mode(ON/OFF) of the probe temperature setpoint.

        Args:
            ramping (True/False): Probe temperature setpoint is ON (TRUE) or OFF (FALSE). If not included, then we
                query the existing state of the ramping.

        Returns:
            (Boolean): Probe temperature setpoint is ON (TRUE) or OFF (FALSE).
        """
        dev=self.selectedDevice(c)
        if ramping is not None:
            if ramping is True:
                state = "ON"
            else:
                state = "OFF"
            yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:RENA:"+state+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:MB1.T1:TEMP:LOOP:RENA\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        if ans=="ON":
            reply=True
        elif ans=="OFF":
            reply=False
        else:
            reply=None
        returnValue(reply)
            
    @setting(537, 'pressure', returns = 'v')
    def pressure(self, c):
        """Query the value of the VTI pressure

        Returns:
            (Value[mbar]): VTI pressure.
        """
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB5.P1:PRES:SIG:PRES"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-2]
        returnValue(float(ans))
        
    @setting(538, 'Pressure setpoint', setpoint = 'v', returns = 'v')
    def pressure_setpoint(self, c, setpoint=None):
        """Set or get VTI pressure setpoint.

        Args:
            setpoint (Value[mbar]): VTI pressure setpoint. If not included, then we
                query the VTI pressure setpoint.

        Returns:
            (Value[mbar]): VTI pressure setpoint.
        """
        dev=self.selectedDevice(c)
        if setpoint is not None:   
            yield dev.write("SET:DEV:DB5.P1:TEMP:LOOP:TSET:"+str(setpoint)+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB5.P1:TEMP:LOOP:TSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-2]
        returnValue(float(ans))
              
    @setting(540, 'Ramp pressure setpoint', ramping = 'b', returns = 'b')
    def ramp_pressure_setpoint(self, c, ramping=None):
        """Set or get ramping mode(ON/OFF) of the VTI pressure setpoint.

        Args:
            ramping (True/False): Pressure setpoint ramping is ON (TRUE) or OFF (FALSE). If not included, then we
                query the existing state of the ramping.

        Returns:
            (Boolean): Pressure setpoint ramping is ON (TRUE) or OFF (FALSE).
        """
        dev=self.selectedDevice(c)
        if ramping is not None:
            if ramping is True:
                state = "ON"
            else:
                state = "OFF"
            yield dev.write("SET:DEV:DB5.P1:PRES:LOOP:SWMD:"+state+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB5.P1:PRES:LOOP:SWMD"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        if ans=="ON":
            reply=True
        elif ans=="OFF":
            reply=False
        else:
            reply=None
        returnValue(reply)
        
    @setting(545, 'VTI temperature setpoint', setpoint = 'v', returns='v')
    def vti_temperature_setpoint(self, c, setpoint=None):
        """Set or get the VTI temperature setpoint.

        Args:
            setpoint (Value[K]): VTI temperature setpoint. If not included, then we
                query the existing VTI temperature setpoint.

        Returns:
            (Value[K]): VTI temperature setpoint.
        """
        dev=self.selectedDevice(c)
        if setpoint is not None:
            dev.write("SET:DEV:MB1.T1:TEMP:LOOP:TSET:"+str(setpoint)+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:MB1.T1:TEMP:LOOP:TSET"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))  
        
    @setting(546, 'Probe heater power', returns='v')
    def probe_heater_power(self, c):
        """Query the probe heater power

        Returns:
            (Value[W]): Probe heater power.
        """
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB3.H1:HTR:SIG:POWR"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))
        
    @setting(547, 'VTI heater power', returns='v')
    def vti_heater_power(self, c):
        """Query the position of the vti heater power

        Returns:
            (Value[W]): VTI heater power.
        """
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:MB0.H1:HTR:SIG:POWR"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))
        
    @setting(548, 'Needle valve position', returns = 'v')
    def needle_valve_position(self, c):
        """Query the position of the needle valve

        Returns:
            (Value[%]): Position of the needle valve.
        """
        dev=self.selectedDevice(c)
        yield dev.write("READ:DEV:DB4.G1:AUX:SIG:PERC"+"\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        ans = ans[:-1]
        returnValue(float(ans))
        
        #below commands haven't been tested
        
    @setting(549, 'Ramp probe temperature setpoint', enabled = 'b', returns='b')
    def probe_temperature_pid_control(self,c, enabled=None):
        """Enable(Auto) or Disable(MANUAL) the PID control for probe temperature.

        Args:
            enabled (True/False): Probe temperature PID control is enabled "AUTO" (TRUE) or disabled "MANUAL" (FALSE). If not included, then we
                query the state of the PID control.

        Returns:
            (Boolean): Probe temperature PID control is AUTO (TRUE) or MANUAL (FALSE).
        """
        dev=self.selectedDevice(c)
        if ramping is not None:
            if ramping is True:
                state = "ON"
            else:
                state = "OFF"
            yield dev.write("SET:DEV:DB8.T1:TEMP:LOOP:ENAB:"+state+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:DB8.T1:TEMP:LOOP:ENAB\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        if ans=="ON":
            reply=True
        elif ans=="OFF":
            reply=False
        else:
            reply=None
        returnValue(reply)
        
    @setting(550, 'Probe temperature pid control', enabled = 'b', returns='b')
    def probe_temperature_pid_control(self,c, enabled=None):
        """Enable(Auto) or Disable(MANUAL) the PID control for VTI temperature.

        Args:
            enabled (True/False): VTI temperature PID control is enabled "AUTO" (TRUE) or disabled "MANUAL" (FALSE). If not included, then we
                query the state of the PID control.

        Returns:
            (Boolean): VTI temperature PID control is AUTO (TRUE) or MANUAL (FALSE).
        """
        dev=self.selectedDevice(c)
        if ramping is not None:
            if ramping is True:
                state = "ON"
            else:
                state = "OFF"
            yield dev.write("SET:DEV:MB1.T1:TEMP:LOOP:ENAB:"+state+"\n")
            ans = yield dev.read()
        yield dev.write("READ:DEV:MB1.T1:TEMP:LOOP:ENAB\n")
        ans = yield dev.read()
        ANS = ans.split(':')
        ans = ANS[-1]
        if ans=="ON":
            reply=True
        elif ans=="OFF":
            reply=False
        else:
            reply=None
        returnValue(reply)
        
        
__server__ = ITCServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
