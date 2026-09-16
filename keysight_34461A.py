# Based on agilent_34401A_dmm.py, Copyright (C) 2007 Matthew Neeley.
# Copyright (C) 2026 Polshyn Lab (additions and modifications)
# Author: Gregory Polshyn
# Modified: 2026-09-09
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
### BEGIN NODE INFO
[info]
name = Keysight 34461A
version = 1.1
description = Keysight Truevolt 34460A/34461A/34465A/34470A multimeters via USB/VISA

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO

Connect the rear USB port and enable USB SCPI on the instrument. Install a
VISA implementation (for example Keysight IO Libraries Suite) and PyVISA
on the computer running gpib_server.py. Start the LabRAD manager,
gpib_device_manager.py, gpib_server.py, and this server. The existing GPIB
Bus server supports USB instruments; no serial server or COM port is used.
Connect the instrument before starting the bus, or call its refresh_devices
setting after connecting it (this repository disables periodic discovery).

Client example:
    dmm = cxn.keysight_34461a
    dmm.list_devices()
    dmm.select_device(0)
    voltage = dmm.voltage()

SCPI reference: Keysight Truevolt Operating and Service Guide, 9018-03876,
pages 202 (READ?), 239 and 248 (CONFigure), 280 (current),
283 (resistance), and 285 (voltage). MEASure resets measurement and trigger
settings to defaults. CONFigure followed by READ? allows repeated readings
with the selected range and resolution. No reset is sent on connection.
Additional references: pages 197-199 (buffer acquisition), 246 (resistance
configuration), 325/344/379 (NPLC), and 385 (acquisition status).

Supports 34460A, 34461A, 34465A, and 34470A identification strings from
Keysight and Agilent. Exposes their shared measurement capabilities:
integration_time accepts the common NPLC values; configure_resistance
supports up to 100 Mohms; buffered acquisitions are limited to 1000 samples.
The larger buffers and additional ranges/NPLC values on higher models are
not exposed by these settings.
"""

import math

import labrad.units as units
from labrad.gpib import GPIBManagedServer
from labrad.server import setting
from twisted.internet.defer import returnValue


def _volts(value):
    """Accept LabRAD voltage quantities and the numeric Python defaults."""
    return float(value['V']) if isinstance(value, units.Value) else float(value)


def _single_reading(response):
    """Reject multi-reading responses instead of silently discarding samples."""
    if isinstance(response, bytes):
        response = response.decode('ascii')
    response = response.strip()
    if ',' in response:
        raise ValueError('Expected one reading; check sample and trigger counts.')
    try:
        value = float(response)
    except ValueError:
        raise ValueError('Invalid DMM reading: {!r}'.format(response)) from None
    if not math.isfinite(value):
        raise ValueError('Non-finite DMM reading: {!r}'.format(response))
    # Preserve the documented overload sentinel (9.9E37), as in the template.
    return value


class Keysight34461AServer(GPIBManagedServer):
    name = 'Keysight 34461A'
    deviceName = ['Keysight Technologies 34460A',
                  'Keysight Technologies 34461A',
                  'Keysight Technologies 34465A',
                  'Keysight Technologies 34470A',
                  'Agilent Technologies 34460A',
                  'Agilent Technologies 34461A',
                  'Agilent Technologies 34465A',
                  'Agilent Technologies 34470A']

    @setting(10, AC='b', returns='v[V]')
    def voltage(self, c, AC=False):
        """
        voltage(AC=False)

        Measure voltage in volts, using autorange and default settings.
            AC: False for DC, True for AC.
            Returns: voltage in V; 9.9E37 indicates overload.

        Measure DC voltage.
            voltage = dmm.voltage()
        """
        dev = self.selectedDevice(c)
        response = yield dev.query('MEAS:VOLT:{}?'.format('AC' if AC else 'DC'))
        returnValue(_single_reading(response) * units.V)

    @setting(11, AC='b', returns='v[A]')
    def current(self, c, AC=False):
        """
        current(AC=False)

        Measure current in amperes, using autorange and default settings.
            AC: False for DC, True for AC. Use the current input terminal.
            Returns: current in A; 9.9E37 indicates overload.

        Measure DC current.
            current = dmm.current()
        """
        dev = self.selectedDevice(c)
        response = yield dev.query('MEAS:CURR:{}?'.format('AC' if AC else 'DC'))
        returnValue(_single_reading(response) * units.A)

    @setting(12, fourWire='b', returns='v[Ohm]')
    def resistance(self, c, fourWire=False):
        """
        resistance(fourWire=False)

        Measure resistance in ohms, using autorange and default settings.
            fourWire: False for 2-wire; True for 4-wire using sense leads.
            Returns: resistance in Ohm; 9.9E37 indicates overload.

        Measure 4-wire resistance.
            resistance = dmm.resistance(True)
        """
        dev = self.selectedDevice(c)
        response = yield dev.query('MEAS:{}?'.format('FRES' if fourWire else 'RES'))
        returnValue(_single_reading(response) * units.Ohm)

    @setting(13, vRange='v[V]', resolution='v[V]', returns='')
    def configure_voltage(self, c, vRange=10, resolution=0.0001):
        """
        configure_voltage(vRange=10, resolution=0.0001)

        Configure DC voltage without starting a measurement. Resets trigger
        settings to one immediate reading; disables math and null functions.
            vRange: range in V: 0.1, 1, 10, 100, or 1000.
            resolution: positive resolution in V, not digits or NPLC.
                The instrument selects the supported integration time.

        Select the 10 V range with 100 uV resolution.
            dmm.configure_voltage(10.0, 0.0001)
        """
        voltage_range = _volts(vRange)
        voltage_resolution = _volts(resolution)
        if voltage_range not in (0.1, 1.0, 10.0, 100.0, 1000.0):
            raise ValueError('vRange must be 0.1, 1, 10, 100, or 1000 V.')
        if not math.isfinite(voltage_resolution) or voltage_resolution <= 0:
            raise ValueError('resolution must be a positive finite voltage.')
        dev = self.selectedDevice(c)
        yield dev.write('CONF:VOLT:DC {:.12g},{:.12g}'.format(
            voltage_range, voltage_resolution))

    @setting(14, returns='v[V]')
    def read_voltage(self, c):
        """
        read_voltage()

        Start and return one voltage measurement with the current settings.
        Call configure_voltage first. The instrument must remain in voltage
        mode with sample and trigger counts of one. External triggering can
        make this query wait for a trigger or time out.
            Returns: voltage in V; 9.9E37 indicates overload.

        Read voltage using the previously configured range and resolution.
            voltage = dmm.read_voltage()
        """
        dev = self.selectedDevice(c)
        response = yield dev.query('READ?')
        returnValue(_single_reading(response) * units.V)

    @setting(15, nplc='v', returns='v')
    def integration_time(self, c, nplc=None):
        """
        integration_time(nplc=None)

        Read/set integration time for the active DC voltage, DC current,
        resistance, or temperature function. Not available for AC measurements.
            nplc: 0.02, 0.2, 1, 10, or 100 power-line cycles, NOT seconds.
                One cycle is 20 ms at 50 Hz or 16.67 ms at 60 Hz.
            Returns: actual NPLC. Omit nplc to query.
        Configure the measurement first: MEAS? and CONF commands reset NPLC.

        Set the active function to 10 power-line cycles.
            actual_nplc = dmm.integration_time(10)
        """
        if nplc is not None:
            nplc = float(nplc)
            if nplc not in (0.02, 0.2, 1, 10, 100):
                raise ValueError('nplc must be 0.02, 0.2, 1, 10, or 100.')
        dev = self.selectedDevice(c)
        function = (yield dev.query('FUNC?')).strip().strip('"').upper()
        commands = {'VOLT': 'VOLT:DC', 'VOLT:DC': 'VOLT:DC',
                    'VOLT:DC:RAT': 'VOLT:DC', 'CURR': 'CURR:DC',
                    'CURR:DC': 'CURR:DC', 'RES': 'RES', 'FRES': 'FRES',
                    'TEMP': 'TEMP'}
        if function not in commands:
            raise ValueError('NPLC is not supported for the active function: ' + function)
        command = commands[function] + ':NPLC'
        query = command + '?'
        if nplc is not None:
            query = '{} {:.12g};:{}'.format(command, nplc, query)
        response = yield dev.query(query)
        returnValue(_single_reading(response))

    @setting(16, fourWire='b', resistance_range='v[Ohm]',
             resolution='v[Ohm]', returns='')
    def configure_resistance(self, c, fourWire=False, resistance_range=None,
                             resolution=None):
        """
        configure_resistance(fourWire=False, resistance_range=None, resolution=None)

        Configure resistance without taking a reading. Resets trigger settings
        to one immediate reading and resets NPLC, math, and null settings.
            fourWire: False for 2-wire; True for 4-wire using sense leads.
            resistance_range: 100, 1e3, 1e4, 1e5, 1e6, 1e7, or 1e8 ohms.
                Omit for autorange.
            resolution: positive value in ohms; requires a fixed range.
                Omit for the default resolution (10 NPLC).

        Configure 4-wire resistance on the 1 kohm range.
            dmm.configure_resistance(True, 1000.0)
        """
        command = 'CONF:{}'.format('FRES' if fourWire else 'RES')
        if resistance_range is not None:
            resistance_range = (float(resistance_range['Ohm'])
                                if isinstance(resistance_range, units.Value)
                                else float(resistance_range))
            if resistance_range not in (100, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8):
                raise ValueError('Resistance range must be 100 ohms through 100 Mohms in decade steps.')
            command += ' {:.12g}'.format(resistance_range)
        if resolution is not None:
            if resistance_range is None:
                raise ValueError('A fixed resistance_range is required with resolution.')
            resolution = (float(resolution['Ohm']) if isinstance(resolution, units.Value)
                          else float(resolution))
            if not math.isfinite(resolution) or resolution <= 0:
                raise ValueError('resolution must be positive and finite, in ohms.')
            command += ',{:.12g}'.format(resolution)
        yield self.selectedDevice(c).write(command)

    @setting(17, returns='v[A]')
    def read_current(self, c):
        """
        read_current()

        Start one current reading using existing settings; returns amperes.
        First select AC/DC current using current(), the front panel, or SCPI.
        Sample and trigger counts must be one. Does not reset NPLC.

        Read current with the existing configuration.
            current = dmm.read_current()
        """
        dev = self.selectedDevice(c)
        function = (yield dev.query('FUNC?')).strip().strip('"').upper()
        if function not in ('CURR', 'CURR:DC', 'CURR:AC'):
            raise ValueError('Configure current measurement before calling read_current().')
        response = yield dev.query('READ?')
        returnValue(_single_reading(response) * units.A)

    @setting(18, returns='v[Ohm]')
    def read_resistance(self, c):
        """
        read_resistance()

        Start one 2-/4-wire resistance reading using existing settings;
        returns ohms. Configure resistance first, with sample and trigger
        counts of one. Does not reset NPLC.

        Read resistance with the existing configuration.
            resistance = dmm.read_resistance()
        """
        dev = self.selectedDevice(c)
        function = (yield dev.query('FUNC?')).strip().strip('"').upper()
        if function not in ('RES', 'FRES'):
            raise ValueError('Configure resistance measurement before calling read_resistance().')
        response = yield dev.query('READ?')
        returnValue(_single_reading(response) * units.Ohm)

    @setting(19, returns='s')
    def system_error(self, c):
        """
        system_error()

        Read and remove the oldest error as a code/message string.
        A zero code means the queue is empty; this does not clear other errors.

        Check for a rejected instrument setting.
            error = dmm.system_error()
        """
        response = yield self.selectedDevice(c).query('SYST:ERR?')
        returnValue(response.strip())

    @setting(20, sample_count='i', returns='')
    def initiate_buffer_measurement(self, c, sample_count=1):
        """
        initiate_buffer_measurement(sample_count=1)

        Start an immediate buffered acquisition and return without waiting.
        Preserves the measurement function, range, resolution, and NPLC.
        Aborts any earlier acquisition, clears old readings, selects immediate
        triggering with one trigger, and leaves the new sample count configured.
            sample_count: integer from 1 to 1000 (common limit across models).
        Do not call MEAS?, READ?, or reconfigure until results are retrieved.

        Acquire 100 readings using the current measurement configuration.
            dmm.initiate_buffer_measurement(100)
        """
        if not isinstance(sample_count, int) or isinstance(sample_count, bool) or not 1 <= sample_count <= 1000:
            raise ValueError('sample_count must be an integer from 1 to 1000.')
        yield self.selectedDevice(c).write(
            'ABOR;:TRIG:SOUR IMM;:TRIG:COUN 1;:SAMP:COUN {};:INIT'.format(sample_count))

    @setting(21, returns='*v[]')
    def get_buffer_measurement_results(self, c):
        """
        get_buffer_measurement_results()

        Return buffered readings as a list of numbers in the active function's
        units (V, A, or ohms for voltage, current, or resistance).
        Raises an error if acquisition is still running; retry later.
        Returns [] if memory is empty. FETCh? leaves the readings in memory;
        repeated calls return the same data. Overload is represented by 9.9E37.

        Retrieve readings after the buffered acquisition finishes.
            data = dmm.get_buffer_measurement_results()
        """
        dev = self.selectedDevice(c)
        status = int((yield dev.query('STAT:OPER:COND?')).strip())
        if status & (16 | 32):
            raise RuntimeError('Buffer measurement is still running or waiting for a trigger; retry later.')
        count = int((yield dev.query('DATA:POIN?')).strip())
        if count == 0:
            returnValue([])
        response = yield dev.query('FETC?')
        values = [_single_reading(value) for value in response.strip().split(',')]
        if len(values) != count:
            raise RuntimeError('Buffered reading count changed during retrieval; check for concurrent commands.')
        returnValue(values)

    @setting(22, returns='')
    def abort_buffer_measurement(self, c):
        """
        abort_buffer_measurement()

        Abort acquisition or a trigger wait and return the trigger system to
        idle. Does not reset the measurement configuration or sample count.

        Stop the active buffered acquisition.
            dmm.abort_buffer_measurement()
        """
        yield self.selectedDevice(c).write('ABOR')


__server__ = Keysight34461AServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
