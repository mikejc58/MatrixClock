# SPDX-FileCopyrightText: 2016 Philip R. Moyer for Adafruit Industries
# SPDX-FileCopyrightText: 2016 Radomir Dopieralski for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# pylint: disable=too-few-public-methods

"""
`adafruit_ds1307` - DS1307 Real Time Clock module
=================================================

## modified to allow Square Wave Output frequency to be selected
## Mike Corrigan 

CircuitPython library to support DS1307 Real Time Clock (RTC).

This library supports the use of the DS1307-based RTC in CircuitPython.

Beware that most CircuitPython compatible hardware are 3.3v logic level! Make
sure that the input pin is 5v tolerant.

* Author(s): Philip R. Moyer and Radomir Dopieralski for Adafruit Industries

Implementation Notes
--------------------

**Hardware:**

* Adafruit `DS1307 RTC breakout <https://www.adafruit.com/products/3296>`_ (Product ID: 3296)

**Software and Dependencies:**

* Adafruit CircuitPython firmware (0.8.0+) for the ESP8622 and M0-based boards:
    https://github.com/adafruit/circuitpython/releases
* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

**Notes:**

#.  Milliseconds are not supported by this RTC.
#.  Alarms and timers are not supported by this RTC.
#.  Datasheet: https://datasheets.maximintegrated.com/en/ds/DS1307.pdf

"""

from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_register import i2c_bit
from adafruit_register import i2c_bits
from adafruit_register import i2c_bcd_datetime

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_DS1307.git"


class DS1307:
    """Interface to the DS1307 RTC."""

    disable_oscillator = i2c_bit.RWBit(0x0, 7)
    """True if the oscillator is disabled."""

    datetime_register = i2c_bcd_datetime.BCDDateTimeRegister(0x00)
    """Current date and time."""

    _square_wave_control = i2c_bits.RWBits(5, 0x07, 0)
    """reg 0x07, bits 0:1 identify the square wave frequency, bit 4 = 1"""
    
    _r5b7 = i2c_bit.RWBit(0x05, 7)
    """reg 0x05, bit 7 used to distinguish among ds1307, pcf8523 and ds3231"""
    _r10b7 = i2c_bit.RWBit(0x10, 7)
    """reg 0x10, bit 7 used to distinguish amont ds1307, pcf8523 and ds3231"""

    def __init__(self, i2c_bus):
        self.i2c_device = I2CDevice(i2c_bus, 0x68)
        chip = self.chip_identity
        expected = self.__class__.__name__
        if chip != expected:
            raise ValueError('Expected {}, found {}'.format(expected, chip))

    @property
    def chip_identity(self):
        """identify the RTC chip (distinguishes among DS1307, PCF8523 and DS3231)"""
        r5b7 = self._r5b7
        self._r5b7 = True
        if self._r5b7:          # if r5 bit7 can be set, this must be ds3231
            self._r5b7 = r5b7
            return 'DS3231'
            
        r10b7 = self._r10b7
        self._r10b7 = True
        if self._r10b7:         # if r10 bit7 can be set, this must be ds1307
            self._r10b7 = r10b7
            return 'DS1307'
            
        return 'PCF8523'        # must be pcf8523

    @property
    def datetime(self):
        """Gets the current date and time or sets the current date and time then starts the
        clock."""
        return self.datetime_register

    @datetime.setter
    def datetime(self, value):
        # automatically starts the oscillator
        self.datetime_register = value

    @property
    def square_wave_frequency(self):
        """Return the square wave frequency, 0 if disabled"""
        value = self._square_wave_control
        freq_bits = value & 0x3
        if value == freq_bits:  # if square wave is disabled
            return 0
        freqs = (1, 4096, 8192, 32768)
        return freqs[freq_bits]

    @square_wave_frequency.setter
    def square_wave_frequency(self, frequency):
        """Select the frequency and enable the square wave output"""
        available_frequencies = {0: 0x00, 1: 0x10, 4096: 0x11, 8192: 0x12, 32768: 0x13}
        try:
            code = available_frequencies[frequency]
            self._square_wave_control = code
        except KeyError:
            raise ValueError('square wave frequency {} not available'.format(frequency))
