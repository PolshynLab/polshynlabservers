# Copyright (C) 2026 Polshyn Lab (additions and modifications)
# Author: Gregory Polshyn
# Modified: 2026-09-09
# Based on the earlier serial version of keysight_33500.py (version 1.0)
# and the GPL-licensed LabRAD server templates in this repository.
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
name = Keysight 33500
version = 2.0
description = Keysight 33500 series waveform generator via USB/VISA

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO

Use the rear USB connector with a VISA driver and gpib_server.py, plus
gpib_device_manager.py. No serial server, COM port, or registry Links entry
is needed. Connect before starting the bus, or call its refresh_devices().
The bus also supports LAN/GPIB. This server controls channel 1 only.
Existing setting IDs, names, arguments, and return types are preserved.
No output or instrument settings are changed on connection.

Reference: Agilent 33500 waveform generator.pdf, printed pages 8-9 (models),
12 and 15 (interfaces), 216 (functions), 264-265 (output/load),
270-271 (phase), 325 (angle units), and 326-332 (voltage).
"""

import math

from labrad.gpib import GPIBManagedServer, GPIBDeviceWrapper
from labrad.server import setting
from twisted.internet.defer import returnValue


MODELS = ('33521A', '33522A', '33509B', '33510B', '33511B', '33512B',
          '33519B', '33520B', '33521B', '33522B')

FUNCTIONS = {
    'SIN': 'SIN',
    'SINE': 'SIN',
    'SQU': 'SQU',
    'SQUARE': 'SQU',
    'TRI': 'TRI',
    'TRIANGLE': 'TRI',
    'RAMP': 'RAMP',
    'PULS': 'PULS',
    'PULSE': 'PULS',
    'NOIS': 'NOIS',
    'NOISE': 'NOIS',
    'DC': 'DC',
    'PRBS': 'PRBS',
    'ARB': 'ARB',
}


def _parse_bool_response(response):
    response = response.strip().upper()
    if response in ('1', '+1', 'ON'):
        return True
    if response in ('0', '+0', 'OFF'):
        return False
    raise ValueError('Expected boolean response, got: {}'.format(response))


def _state(value):
    return 'ON' if value else 'OFF'


class Keysight33500Wrapper(GPIBDeviceWrapper):
    def set_and_query(self, command, value=None):
        """Keep a setter and its readback in one atomic bus query."""
        if value is None:
            return self.query(command + '?')
        return self.query('{} {};:{}?'.format(command, value, command))

    def command_and_error(self, command):
        """Send a command and read one error entry in the same bus query."""
        return self.query(command + ';:SYST:ERR?')


class Keysight33500Server(GPIBManagedServer):
    name = 'Keysight 33500'
    deviceName = [manufacturer + ' ' + model
                  for manufacturer in ('Keysight Technologies', 'Agilent Technologies')
                  for model in MODELS]
    deviceWrapper = Keysight33500Wrapper

    @setting(100, returns='s')
    def identify(self, c):
        """Return the instrument identification string."""
        dev = self.selectedDevice(c)
        ans = yield dev.query('*IDN?')
        returnValue(ans)

    @setting(101)
    def reset(self, c):
        """Reset the waveform generator to its factory default state."""
        dev = self.selectedDevice(c)
        yield dev.write('*RST')

    @setting(102)
    def clear_status(self, c):
        """Clear status registers and the error queue."""
        dev = self.selectedDevice(c)
        yield dev.write('*CLS')

    @setting(103, returns='s')
    def system_error(self, c):
        """Read and remove one entry from the system error queue."""
        dev = self.selectedDevice(c)
        ans = yield dev.query('SYST:ERR?')
        returnValue(ans)

    @setting(104, command='s')
    def raw_write(self, c, command):
        """Send a raw SCPI command."""
        dev = self.selectedDevice(c)
        yield dev.write(command)

    @setting(105, command='s', returns='s')
    def raw_query(self, c, command):
        """Send a raw SCPI query and return one response line."""
        dev = self.selectedDevice(c)
        ans = yield dev.query(command)
        returnValue(ans)

    @setting(200, function=['', 's'], returns='s')
    def function(self, c, function=None):
        """Set or get the output waveform function.

        Accepted values: SIN, SQU, TRI, RAMP, PULS, NOIS, DC, PRBS, ARB.
        ARB requires arbitrary-waveform capability and a selected waveform;
        a base 33509B requires an ARB upgrade. Read system_error() if rejected.
        """
        dev = self.selectedDevice(c)
        if function is not None:
            key = function.strip().upper()
            if key not in FUNCTIONS:
                raise ValueError('Unknown waveform function: {}'.format(function))
            function = FUNCTIONS[key]
        ans = yield dev.set_and_query('FUNC', function)
        returnValue(ans)

    @setting(201, frequency=['', 'v'], returns='v')
    def frequency(self, c, frequency=None):
        """Set or get output frequency in Hz."""
        dev = self.selectedDevice(c)
        if frequency is not None:
            frequency = float(frequency)
        ans = yield dev.set_and_query('FREQ', frequency)
        returnValue(float(ans))

    @setting(202, amplitude=['', 'v'], returns='v')
    def amplitude(self, c, amplitude=None):
        """Set or get output amplitude in the currently selected voltage units."""
        dev = self.selectedDevice(c)
        if amplitude is not None:
            amplitude = float(amplitude)
        ans = yield dev.set_and_query('VOLT', amplitude)
        returnValue(float(ans))

    @setting(203, offset=['', 'v'], returns='v')
    def offset(self, c, offset=None):
        """Set or get DC offset in volts, for the configured expected load."""
        dev = self.selectedDevice(c)
        if offset is not None:
            offset = float(offset)
        ans = yield dev.set_and_query('VOLT:OFFS', offset)
        returnValue(float(ans))

    @setting(204, enabled=['', 'b'], returns='b')
    def output(self, c, enabled=None):
        """Set or get output enable state."""
        dev = self.selectedDevice(c)
        ans = yield dev.set_and_query('OUTP', _state(enabled) if enabled is not None else None)
        returnValue(_parse_bool_response(ans))

    @setting(205, load=['', 'v'], returns='s')
    def load(self, c, load=None):
        """Set or get expected output load.

        Pass 1 to 10000 ohms, or query with no argument. Use high_z(True)
        for high impedance (query returns 9.9E37). This changes voltage scaling,
        not the physical 50-ohm source impedance.
        """
        dev = self.selectedDevice(c)
        if load is not None:
            load = float(load)
            if not 1 <= load <= 10000:
                raise ValueError('load must be 1 to 10000 ohms; use high_z(True) for INF.')
        ans = yield dev.set_and_query('OUTP:LOAD', load)
        returnValue(ans)

    @setting(206, units=['', 's'], returns='s')
    def voltage_units(self, c, units=None):
        """Set or get amplitude units: VPP, VRMS, or DBM."""
        dev = self.selectedDevice(c)
        if units is not None:
            units = units.strip().upper()
            if units not in ('VPP', 'VRMS', 'DBM'):
                raise ValueError('Voltage units must be VPP, VRMS, or DBM.')
        ans = yield dev.set_and_query('VOLT:UNIT', units)
        returnValue(ans)

    @setting(207, enabled=['', 'b'], returns='b')
    def high_z(self, c, enabled=None):
        """Set or get whether the expected output load is high impedance."""
        dev = self.selectedDevice(c)
        load = None if enabled is None else ('INF' if enabled else '50')
        ans = yield dev.set_and_query('OUTP:LOAD', load)
        if ans.strip().upper() in ('INF', 'INFINITY'):
            returnValue(True)
        returnValue(float(ans) > 1e6)

    @setting(208, phase=['', 'v'], returns='v')
    def phase(self, c, phase=None):
        """Set or get phase in degrees (-360 to 360); selects UNIT:ANGL DEG.

        Not supported for noise or arbitrary waveforms. Independent of burst
        phase. The angle-unit selection also applies to burst phase commands.
        """
        dev = self.selectedDevice(c)
        command = 'UNIT:ANGL DEG'
        if phase is not None:
            phase = float(phase)
            if not math.isfinite(phase) or not -360 <= phase <= 360:
                raise ValueError('phase must be between -360 and 360 degrees.')
            command += ';:PHAS {}'.format(phase)
        ans = yield dev.query(command + ';:PHAS?')
        returnValue(float(ans))

    @setting(209)
    def phase_reference(self, c):
        """Set the current output phase as the zero-phase reference."""
        dev = self.selectedDevice(c)
        yield dev.write('PHAS:REF')

    @setting(210, frequency='v', amplitude='v', offset='v')
    def apply_sine(self, c, frequency, amplitude, offset=0.0):
        """Configure channel 1: frequency in Hz, amplitude in voltage_units(),
        offset in volts. Preserves output enable and modulation/burst settings.
        Unlike SCPI APPL:SIN, this does not automatically enable the output.
        """
        dev = self.selectedDevice(c)
        yield dev.write('FUNC SIN;:FREQ {};:VOLT {};:VOLT:OFFS {}'.format(
            float(frequency), float(amplitude), float(offset)))

    @setting(211, frequency='v', amplitude='v', offset='v', output='b')
    def configure_sine(self, c, frequency, amplitude, offset=0.0, output=None):
        """Configure channel 1: Hz, amplitude in voltage_units(), offset in V.
        output=None preserves output state; True/False sets it after configuration.
        Modulation/burst settings are preserved. Check system_error() for conflicts.
        """
        dev = self.selectedDevice(c)
        command = 'FUNC SIN;:FREQ {};:VOLT {};:VOLT:OFFS {}'.format(
            float(frequency), float(amplitude), float(offset))
        if output is not None:
            command += ';:OUTP {}'.format(_state(output))
        yield dev.write(command)


__server__ = Keysight33500Server()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
