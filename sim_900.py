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
name = SIM900 
version = 1.0
description = SIM 900 Mainframe with SIM 921 AC Resistance Bridge and SIM 928 Isolated Voltage Source
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
serial_server_name = platform.node() + '_serial_server'

from labrad.server import setting
from labrad.devices import DeviceServer,DeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

TIMEOUT = Value(5,'s')
BAUD    = 115200
PARITY = 'N'
STOP_BITS = 1
BYTESIZE= 8

class serverInfo(object):
    def __init__(self):
        self.deviceName = 'SIM900'
        self.serverName = "SIM900"

    def getDeviceName(self,comPort):
        return "%s (%s)"%(self.serverName, comPort)


class SIM900Wrapper(DeviceWrapper):

    @inlineCallbacks
    def connect(self, server, port):
        """Connect to a device."""
        print('connecting to "%s" on port "%s"...' % (server.name, port), end=' ')
        self.server = server
        self.ctx = server.context()
        self.port = port
        p = self.packet()
        p.open(port)
        print('opened on port "%s"' %self.port)
        p.baudrate(BAUD)
        p.parity(PARITY)
        p.stopbits(STOP_BITS)
        p.bytesize(BYTESIZE)
        p.read()  # clear out the read buffer
        p.timeout(TIMEOUT)
        print(" CONNECTED ")
        yield p.send()
        
    def packet(self):
        """Create a packet in our private context."""
        return self.server.packet(context=self.ctx)

    def shutdown(self):
        """Disconnect from the serial port when we shut down."""
        return self.packet().close().send()

    @inlineCallbacks
    def write(self, code):
        """Write a data value to the temperature controller."""
        yield self.packet().write(code).send()

    @inlineCallbacks
    def read(self):
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
        

class SIM900Server(DeviceServer):
    name = serverInfo().serverName
    deviceName = serverInfo().deviceName
    deviceWrapper = SIM900Wrapper

    @inlineCallbacks
    def initServer(self):
        print('loading config info...', end=' ')
        self.reg = self.client.registry()
        yield self.loadConfigInfo()
        print('done.')
        print(self.serialLinks)
        yield DeviceServer.initServer(self)

    @inlineCallbacks
    def loadConfigInfo(self):
        """Load configuration information from the registry."""
        # reg = self.client.registry
        # p = reg.packet()
        # p.cd(['', 'Servers', 'Heat Switch'], True)
        # p.get('Serial Links', '*(ss)', key='links')
        # ans = yield p.send()
        # self.serialLinks = ans['links']
        reg = self.reg
        yield reg.cd(['', 'Servers', 'SIM900', 'Links'], True)
        dirs, keys = yield reg.dir()
        p = reg.packet()
        print(" created packet")
        print("printing all the keys",keys)
        for k in keys:
            print("k=",k)
            p.get(k, key=k)
            
        ans = yield p.send()
        print("ans=",ans)
        self.serialLinks = dict((k, ans[k]) for k in keys)


    @inlineCallbacks
    def findDevices(self):
        """Find available devices from list stored in the registry."""
        devs = []
        # for name, port in self.serialLinks:
        # if name not in self.client.servers:
        # continue
        # server = self.client[name]
        # ports = yield server.list_serial_ports()
        # if port not in ports:
        # continue
        # devName = '%s - %s' % (name, port)
        # devs += [(devName, (server, port))]
        # returnValue(devs)
        for name, (serServer, port) in list(self.serialLinks.items()):
            if serServer not in self.client.servers:
                continue
            server = self.client[serServer]
            print(server)
            print(port)
            ports = yield server.list_serial_ports()
            print(ports)
            if port not in ports:
                continue
            devName = '%s - %s' % (serServer, port)
            devs += [(devName, (server, port))]

       # devs += [(0,(3,4))]
        returnValue(devs)
    
    @setting(100)
    def connect(self,c,server,port):
        dev=self.selectedDevice(c)
        yield dev.connect(server,port)

    @setting(101,returns='s')
    def ID(self,c):
        dev=self.selectedDevice(c)
        ans=yield dev.query("*IDN?\r")
        returnValue(ans)

    @setting(202,channel='i',voltage='v')
    def DC_set_voltage(self,c,channel,voltage):
        """
        Set the voltage output
        EXAMPLE: SIM.dc_set_voltage(1,1.2)
        """
        dev=self.selectedDevice(c)
        voltage = float("{0:.3f}".format(voltage))
        yield dev.write('SNDT %s,"VOLT %s"\r'%(channel,voltage))

    @setting(203,channel='i',returns='v')
    def DC_get_voltage(self,c,channel):
        """
        Get the voltage output
        EXAMPLE: SIM.dc_set_voltage(1)
        """
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('VOLT?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))
		
    @setting(204,channel='i')
    def DC_output_on(self,c,channel):
        """
        Set the DC voltage output on
        """
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"OPON"\r'%(channel))

    @setting(205,channel='i')
    def DC_output_off(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"OPOF"\r'%(channel))

    @setting(206,channel='i',returns='s')
    def DC_get_output_state(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('EXO?\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(207,channel='i')
    def IVS_reset(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"*RST"\r'%(channel))

    @setting(301,channel='i',freq='v')
    def set_frequency(self,c,channel,freq):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"FREQ %s"\r'%(channel,freq))
	 
    @setting(302,channel='i',returns='v')
    def get_frequency(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('FREQ?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

    @setting(303,channel='i',range='i')
    def set_range(self,c,channel,range):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"RANG %s"\r'%(channel,range))

    @setting(304,channel='i',returns='s')
    def get_range(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('RANG?\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(305,channel='i',excitation='i')
    def set_excitation(self,c,channel,excitation):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"EXCI %s"\r'%(channel,excitation))

    @setting(306,channel='i',returns='s')
    def get_excitation(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('EXCI?\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(307,channel='i')
    def excitation_on(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"EXON 1"\r'%(channel))

    @setting(308,channel='i')
    def excitation_off(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"EXON 0"\r'%(channel))

    @setting(309,channel='i',returns='s')
    def get_excitation_state(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('EXON?\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(310,channel='i',mode='i')
    def set_excitation_mode(self,c,channel,mode):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"MODE %s"\r'%(channel,mode))

    @setting(311,channel='i',returns='s')
    def get_excitation_mode(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('MODE?\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(312,channel='i',time_constant='i')
    def set_time_constant(self,c,channel,time_constant):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"TCON %s"\r'%(channel,time_constant))

    @setting(313,channel='i',returns='s')
    def get_time_constant(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('TCON?\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(314,channel='i',returns='v')
    def measure_voltage(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('VEXC?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

    @setting(315,channel='i',returns='v')
    def measure_current(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('IEXC?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

    @setting(316,channel='i',returns='v')
    def measure_phase(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('PHAS?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

    @setting(317,channel='i',returns='v')
    def measure_resistance(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('RVAL?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

    @setting(318,channel='i',returns='v')
    def measure_temperature(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r'%channel)
        ans=yield dev.query('TVAL?\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

    @setting(319,channel='i')
    def ACRB_reset(self,c,channel):
        dev=self.selectedDevice(c)
        yield dev.write('SNDT %s,"*RST"\r'%channel)

############# Methods for SIM970 Quad DVM ###############################################################################
       
    #Don't change the following functions
    @setting(401, channel='i', returns='s')
    def read_voltage(self, c, channel, voltmeter):
        """
        Read voltage for a specific channel(SIM 970).
        
        Parameters:
        channel: The port on which the module is connected.
        voltmeter (int): The display number (1-4, 0 for all).
        
        Returns:
        str: Measured voltage.
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        ans = yield dev.query('VOLT? %d\r' % voltmeter)
        #ans = yield dev.query('VOLT? 1,100\r')
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(402, channel='i', voltmeter='v', returns='s')
    def read_ground_voltage(self, c, channel, voltmeter):
        """
        Read ground voltage (offset correction) for a specific channel (SIM 970).
        
        Parameters:
        channel: The port on which the module is connected.
        voltmeter (int): The display number (1-4, 0 for all).
        
        Returns:
        str: Measured ground voltage.
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        ans = yield dev.query('VGND? %d\r' % voltmeter)
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(403, channel='i', voltmeter='v', returns='s')
    def read_reference_voltage(self, c, channel, voltmeter):
        """
        Read reference voltage (gain correction) for a specific channel (SIM 970).
        
        Parameters:
        channel: The port on which the module is connected.
        voltmeter (int): The display number (1-4, 0 for all).
        Returns:
        str: Measured reference voltage.
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        ans = yield dev.query('VREF? %d\r' % voltmeter)
        yield dev.write('cometzir\r')
        returnValue(ans)

    @setting(404, returns='s')
    def stop_streaming(self, c, channel):
        """
        Stop the continuous output of multiple VOLT? responses (SIM 970).
        Parameters:
        channel: The port on which the module is connected.
        Returns:
        str: Response from the SIM970 module after stopping streaming.
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        ans = yield dev.write('SOUT\r')
        yield dev.write('cometzir\r')
        returnValue(float(ans))

############# Methods for SIM910 JFET Preamp################################################################
        
    @setting(501, channel='i', returns='s')
    def gain_amp910(self, c, channel, gain=None):
        """
        Sets the gain of the SIM910 JFET amplifier.
        Queries the gain of the SIM910 JFET amplifier.
        
        channel: Amplifier channel to set.
        gain: Gain value to set (1, 2, 5, 10, 20, 50, 100).
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        if gain is not None:
            yield dev.write('GAIN %d\r' % gain)   
        ans = yield dev.query('GAIN?\r')
        yield dev.write('cometzir\r')
        returnValue("Gain set to %s" % ans)
        
    @setting(502, channel='i', returns='s')
    def coupling_amp910(self, c, channel, coupling=None):
        """
        Sets the input coupling of the SIM910 JFET amplifier.
        
        channel: Amplifier channel to set.
        coupling: Coupling value to set (1 for AC, 2 for DC).
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        if coupling is not None:
            yield dev.write('COUP %d\r' % coupling)   
        ans = yield dev.query('COUP?\r')
        yield dev.write('cometzir\r')
        returnValue("Coupling set to %s" % ans)
        
    @setting(503, channel='i', returns='s')
    def input_amp910(self, c, channel, input_val=None):
        """
        Sets the input of the SIM910 JFET amplifier.
        Queries the input of the SIM910 JFET amplifier.
        
        channel: Amplifier channel to set.
        input_val: Input value to set (1 for A, 2 for A-B, 3 for Ground).
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        if input_val is not None:
            yield dev.write('INPT %d\r' % input_val)  
        ans = yield dev.query('INPT?\r')
        yield dev.write('cometzir\r')
        returnValue("Input set to %s" % ans)    
        
    @setting(504, channel='i', returns='s')
    def shield_amp910(self, c, channel, shield=None):
        """
        Sets the input BNC shield configuration of the SIM910 JFET amplifier.
        Queries the input BNC shield configuration of the amplifier.
        
        channel: Amplifier channel to set.
        shield: Shield value to set (1 for Float, 2 for Ground).
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %s,"cometzir"\r' % channel)
        if shield is not None:
            yield dev.write('SHLD %d\r' % shield) 
        ans = yield dev.query('SHLD?\r')
        yield dev.write('cometzir\r')
        returnValue("Shield set to %s" % ans)
        
############# Methods for SIM965 analog filter #############################################################
    
    @setting(6011, channel='i', returns='v')
    def frequency_965(self, c, channel, frequency=None):
        """
        Set the frequency for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.set_frequency(1, 1.23)  # Frequency in Hz
        
        Get the frequency for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.get_frequency965(1)
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %d,"cometzir"\r' % channel)
        if frequency is not None:
            yield dev.write('FREQ %.6f\r' % frequency)
        ans = yield dev.query('FREQ?\r')
        yield dev.write('cometzir\r')
        return(float(ans))
        
    @setting(6021, channel='i', returns='v')
    def filter_type_965(self, c, channel, filter_type=None):
        """
        Set the filter type for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.set_filter_type965(1, 1)  # 0 for BUTTER and #1 for BESSEL
        
        Get the filter type for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.get_filter_type965(1)
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %d,"cometzir"\r' % channel)
        if filter_type is not None:
            yield dev.write('TYPE %d\r' % filter_type)
        ans = yield dev.query('TYPE?\r')
        yield dev.write('cometzir\r')
        return(int(ans))
        
    @setting(6031, channel='i', returns='v')
    def band_pass_965(self, c, channel, pass_band=None):
        """
        Set the filter pass band for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.set_pass_band965(1, 0)  # 0 for Lowpass 1 for Highpass
        
        Get the filter pass band for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.get_pass_band965(1)
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %d,"cometzir"\r' % channel)
        if pass_band is not None:
            yield dev.write('PASS %d\r' % pass_band)
        ans = yield dev.query('PASS?\r')
        yield dev.write('cometzir\r')
        return(int(ans))
        
    @setting(6041, channel='i', returns='v')
    def slope_965(self, c, channel, slope=None):
        """
        Set the filter slope for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.set_slope965(1, 12)  # Slope in dB/octave
        Set the filter stop band rolloff rate to(12, 24, 36, 48) dB/octave
        
        Get the filter slope for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.get_slope965(1)
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %d,"cometzir"\r' % channel)
        if slope is not None:
            yield dev.write('SLPE %d\r' % slope)
        ans = yield dev.query('SLPE?\r')
        yield dev.write('cometzir\r')
        return(int(ans))
    
    @setting(6051, channel='i', returns='v')
    def coupling_965(self, c, channel, coupling=None):
        """
        Set the input coupling for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.set_coupling965(1, 0)  # 0 for AC, 1 for DC
        
        Get the input coupling for the specified channel on the SIM965 filter module.
        EXAMPLE: SIM.get_coupling965(1)
        """
        dev = self.selectedDevice(c)
        yield dev.write('CONN %d,"cometzir"\r' % channel)
        if coupling is not None:
            yield dev.write('COUP %d\r' % coupling)
        ans = yield dev.query('COUP?\r')
        yield dev.write('cometzir\r')
        return(int(ans))

    @setting(701, channel = 'i', returns='s')
    def Identify(self, c, channel):
        dev=self.selectedDevice(c)
        yield dev.write('CONN %d,"cometzir"\r' % channel)
        ans=yield dev.query("*IDN?\r")
        yield dev.write('cometzir\r')
        returnValue(ans)





__server__ = SIM900Server()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)