# SPDX-FileCopyrightText: 2016 Philip R. Moyer for Adafruit Industries
# SPDX-FileCopyrightText: 2016 Radomir Dopieralski for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_ds3231` - DS3231 Real Time Clock module
=================================================
CircuitPython library to support DS3231 Real Time Clock (RTC).

This library supports the use of the DS3231-based RTC in CircuitPython.

Author(s): Philip R. Moyer and Radomir Dopieralski for Adafruit Industries.

Implementation Notes
--------------------

**Hardware:**

* Adafruit `DS3231 Precision RTC FeatherWing <https://www.adafruit.com/products/3028>`_
  (Product ID: 3028)

* Adafruit `DS3231 RTC breakout <https://www.adafruit.com/products/3013>`_ (Product ID: 3013)
* Adafruit `ChronoDot - Ultra-precise Real Time Clock -
  v2.1 <https://www.adafruit.com/products/255>`_ (Product ID: 3013)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the ESP8622 and M0-based boards:
  https://github.com/adafruit/circuitpython/releases

* Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

**Notes:**

#. Milliseconds are not supported by this RTC.
#. Datasheet: https://datasheets.maximintegrated.com/en/ds/DS3231.pdf

"""
from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_register import i2c_bit
from adafruit_register import i2c_bits
from adafruit_register import i2c_bcd_alarm
from adafruit_register import i2c_bcd_datetime

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_DS3231.git"

# pylint: disable-msg=too-few-public-methods
# pylint: disable-msg=too-many-instance-attributes
class DS3231:
    """Interface to the DS3231 RTC."""

    lost_power = i2c_bit.RWBit(0x0F, 7)
    """True if the device has lost power since the time was set."""

    disable_oscillator = i2c_bit.RWBit(0x0E, 7)
    """True if the oscillator is disabled."""

    datetime_register = i2c_bcd_datetime.BCDDateTimeRegister(0x00)
    """Current date and time."""

    alarm1 = i2c_bcd_alarm.BCDAlarmTimeRegister(0x07)
    """Alarm time for the first alarm."""

    alarm1_interrupt = i2c_bit.RWBit(0x0E, 0)
    """True if the interrupt pin will output when alarm1 is alarming."""

    alarm1_status = i2c_bit.RWBit(0x0F, 0)
    """True if alarm1 is alarming. Set to False to reset."""

    alarm2 = i2c_bcd_alarm.BCDAlarmTimeRegister(0x0B, has_seconds=False)
    """Alarm time for the second alarm."""

    alarm2_interrupt = i2c_bit.RWBit(0x0E, 1)
    """True if the interrupt pin will output when alarm2 is alarming."""

    alarm2_status = i2c_bit.RWBit(0x0F, 1)
    """True if alarm2 is alarming. Set to False to reset."""

    _square_wave_control = i2c_bits.RWBits(3, 0x0E, 2)
    """reg 0x0e, bits 3:4 identify the square wave frequency, bit 2 is disable"""

    _r5b7 = i2c_bit.RWBit(0x05, 7)
    """reg 0x05, bit 7 used to distinguish among ds1307, pcf8523 and ds3231"""
    _r10b7 = i2c_bit.RWBit(0x10, 7)
    """reg 0x10, bit 7 used to distinguish among ds1307, pcf8523 and ds3231"""

    # pylint: disable=unexpected-keyword-arg
    _calibration = i2c_bits.RWBits(8, 0x10, 0, 1, signed=True)

    _temperature = i2c_bits.RWBits(
        10, 0x11, 6, register_width=2, lsb_first=False, signed=True
    )
    # pylint: enable=unexpected-keyword-arg

    _busy = i2c_bit.ROBit(0x0F, 2)
    _conv = i2c_bit.RWBit(0x0E, 5)

    def __init__(self, i2c):
        self.i2c_device = I2CDevice(i2c, 0x68)
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
        """Gets the current date and time or sets the current date and time
        then starts the clock."""
        return self.datetime_register

    @datetime.setter
    def datetime(self, value):
        self.datetime_register = value
        self.disable_oscillator = False
        self.lost_power = False

    @property
    def temperature(self):
        """Returns the last temperature measurement.  Temperature is updated
        only every 64 seconds, or when a conversion is forced."""
        return self._temperature / 4

    def force_temperature_conversion(self):
        """Forces a conversion and returns the new temperature"""
        while self._busy:
            pass  # Wait for any normal in-progress conversion to complete
        self._conv = True
        while self._conv:
            pass  # Wait for manual conversion request to complete
        return self.temperature

    @property
    def square_wave_frequency(self):
        """Return the square wave frequency, 0 if not enabled"""
        value = self._square_wave_control
        freqs = (1, 0, 1024, 0, 4096, 0, 8192, 0)
        return freqs[value]

    @square_wave_frequency.setter
    def square_wave_frequency(self, frequency):
        available_frequencies = {0: 1, 1: 0, 1024: 2, 4096: 4, 8192: 6}
        try:
            code = available_frequencies[frequency]
            self._square_wave_control = code
        except KeyError:
            raise ValueError('square wave frequency {} not available'.format(frequency))

    @property
    def calibration(self):
        """Calibrate the frequency of the crystal oscillator by adding or
        removing capacitance.  The datasheet calls this the Aging Offset.
        Calibration values range from -128 to 127; each step is approximately
        0.1ppm, and positive values decrease the frequency (increase the
        period).  When set, a temperature conversion is forced so the result of
        calibration can be seen directly at the 32kHz pin immediately"""
        return self._calibration

    @calibration.setter
    def calibration(self, value):
        self._calibration = value
        self.force_temperature_conversion()
