# SPDX-FileCopyrightText: 2016 Philip R. Moyer for Adafruit Industries
# SPDX-FileCopyrightText: 2016 Radomir Dopieralski for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_pcf8523` - PCF8523 Real Time Clock module
====================================================

This library supports the use of the PCF8523-based RTC in CircuitPython. It
contains a base RTC class used by all Adafruit RTC libraries. This base
class is inherited by the chip-specific subclasses.

Functions are included for reading and writing registers and manipulating
datetime objects.

Author(s): Philip R. Moyer and Radomir Dopieralski for Adafruit Industries.
Date: November 2016
Affiliation: Adafruit Industries

Implementation Notes
--------------------

**Hardware:**

* Adafruit `Adalogger FeatherWing - RTC + SD Add-on <https://www.adafruit.com/products/2922>`_
  (Product ID: 2922)
* Adafruit `PCF8523 RTC breakout <https://www.adafruit.com/products/3295>`_ (Product ID: 3295)

**Software and Dependencies:**

* Adafruit CircuitPython firmware: https://github.com/adafruit/circuitpython/releases
* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

**Notes:**

#. Milliseconds are not supported by this RTC.
#. Datasheet: http://cache.nxp.com/documents/data_sheet/PCF8523.pdf

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PCF8523.git"

from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_register import i2c_bit
from adafruit_register import i2c_bits
from adafruit_register import i2c_bcd_alarm
from adafruit_register import i2c_bcd_datetime

STANDARD_BATTERY_SWITCHOVER_AND_DETECTION = 0b000
BATTERY_SWITCHOVER_OFF = 0b111


class PCF8523:
    """Interface to the PCF8523 RTC."""

    lost_power = i2c_bit.RWBit(0x03, 7)
    """True if the device has lost power since the time was set."""

    disable_oscillator = i2c_bit.RWBit(0x00, 5)
    """True if the oscillator is disabled."""

    _square_wave_control = i2c_bits.RWBits(3, 0x0F, 3)
    """reg 0x0F, bits 3:5 identify the square wave frequency"""

    _r13b0 = i2c_bit.ROBit(0x13, 0)
    """reg 0x13, bit 0 used to distinguish ds3231"""
    _r3fb0 = i2c_bit.RWBit(0x3f, 0)
    """reg 0x3f, bit 0 used to distinguish between ds1307 and pcf8523"""
    
    power_management = i2c_bits.RWBits(3, 0x02, 5)
    """Power management state that dictates battery switchover, power sources
    and low battery detection. Defaults to BATTERY_SWITCHOVER_OFF (0b111)."""

    # The False means that day comes before weekday in the registers. The 0 is
    # that the first day of the week is value 0 and not 1.
    datetime_register = i2c_bcd_datetime.BCDDateTimeRegister(0x03, False, 0)
    """Current date and time."""

    # The False means that day and weekday share a register. The 0 is that the
    # first day of the week is value 0 and not 1.
    alarm = i2c_bcd_alarm.BCDAlarmTimeRegister(
        0x0A, has_seconds=False, weekday_shared=False, weekday_start=0
    )
    """Alarm time for the first alarm."""

    alarm_interrupt = i2c_bit.RWBit(0x00, 1)
    """True if the interrupt pin will output when alarm is alarming."""

    alarm_status = i2c_bit.RWBit(0x01, 3)
    """True if alarm is alarming. Set to False to reset."""

    battery_low = i2c_bit.ROBit(0x02, 2)
    """True if the battery is low and should be replaced."""

    high_capacitance = i2c_bit.RWBit(0x00, 7)
    """True for high oscillator capacitance (12.5pF), otherwise lower (7pF)"""

    calibration_schedule_per_minute = i2c_bit.RWBit(0x0E, 7)
    """False to apply the calibration offset every 2 hours (1 LSB = 4.340ppm);
    True to offset every minute (1 LSB = 4.069ppm).  The default, False,
    consumes less power.  See datasheet figures 28-31 for details."""

    calibration = i2c_bits.RWBits(  # pylint: disable=unexpected-keyword-arg
        7, 0xE, 0, signed=True
    )
    """Calibration offset to apply, from -64 to +63.  See the PCF8523 datasheet
    figure 18 for the offset calibration calculation workflow."""

    def __init__(self, i2c_bus):
        self.i2c_device = I2CDevice(i2c_bus, 0x68)
        chip = self.chip_identity
        expected = self.__class__.__name__
        if chip != expected:
            raise RuntimeError('Expected {}, found {} at i2c address 0x68'.format(expected, chip))

    @property
    def chip_identity(self):
        """identify the RTC chip (distinguishes among DS1307, PCF8523 and DS3231)"""
        try:
            r13b0 = self._r13b0
        except OSError:
            return 'DS3231'
        else:
            r3fb0 = self._r3fb0
            self._r3fb0 = not r3fb0
            if r3fb0 != self._r3fb0:
                self._r3fb0 = r3fb0
                return 'DS1307'
        return 'PCF8523'

    @property
    def datetime(self):
        """Gets the current date and time or sets the current date and time then starts the
        clock."""
        return self.datetime_register

    @datetime.setter
    def datetime(self, value):
        # Required to enable switching to battery
        self.power_management = STANDARD_BATTERY_SWITCHOVER_AND_DETECTION
        # Automatically sets lost_power to false.
        self.datetime_register = value
        self.disable_oscillator = False

    @property
    def square_wave_frequency(self):
        """Return the square wave frequency, 0 if not enabled"""
        value = self._square_wave_control
        freqs = (1, 32, 1024, 4096, 8192, 16384, 32768, 0)
        return freqs[value]

    @square_wave_frequency.setter
    def square_wave_frequency(self, frequency):
        available_frequencies = {0: 7, 1: 6, 32: 5, 1024: 4, 4096: 3, 8192: 2, 16384: 1, 32768: 0}
        try:
            code = available_frequencies[frequency]
            self._square_wave_control = code
        except KeyError:
            raise ValueError('square wave frequency {} not available'.format(frequency))
