# Matrix Clock

# clock.py encapsulates the handling of the hardware RTC
# it supports ds1307, ds3231 and pcf8523 clocks, and requires
# access to the SQW (Square Wave) outputs.  The SQW pin on
# the clock boards must be wired to one of the available
# pins on the Adafruit Matrix Portal board (A0, A1, A2, A3, A4)

# It will dynamically determine which of these chips is connected
# and load the appropriate driver

from adafruit_register import i2c_bit
from adafruit_bus_device.i2c_device import I2CDevice
import sys
import digitalio
import board
import busio
import time

import logger


# Identifies which clock chip is available
class Clock:
    class Chip:
        _r5b7 = i2c_bit.RWBit(0x05, 7)
        _r10b7 = i2c_bit.RWBit(0x10, 7)
        _r12b0 = i2c_bit.RWBit(0x12, 0)
        
        def __init__(self, i2c_bus):
            self.i2c_device = I2CDevice(i2c_bus, 0x68)
            
        def identify(self):
            Clock_chip = None
            chip = self._identity()
            log.message("Clock chip identified as {}".format(chip))
            if chip == 'DS3231':            
                from adafruit_ds3231 import DS3231 as Clock_chip
            elif chip == 'DS1307':
                from adafruit_ds1307 import DS1307 as Clock_chip
            elif chip == 'PCF8523':
                from adafruit_pcf8523 import PCF8523 as Clock_chip
            else:   
                log.message("Can not identify the device at i2c address 0x68")
                
            return Clock_chip
        
        def _identity(self):
            # Reg 0x05, bit 7 is the 'century' bit in ds3231, and unimplemented in ds1307 and pcf8523
            # if it can be modified, this could be a ds3231, but not ds1307 nor pcf8523
            r5b7 = self._r5b7
            self._r5b7 = True
            if self._r5b7:
                self._r5b7 = r5b7
                return 'DS3231'
            # Reg 0x10, bit 7 is not implemented in pcf8523, and is a user memory location in ds1307
            # if it can be modified, this could be a ds1307, but not pcf8523   
            r10b7 = self._r10b7
            self._r10b7 = True
            if self._r10b7:
                self._r10b7 = r10b7
                return 'DS1307'
            # Reg 0x12, bit 0 is part of pcf8523's TimerB frequency control
            # if it can be modified, this could be pcf8523    
            r12b0 = self._r12b0
            test = not r12b0
            self._r12b0 = test
            if self._r12b0 == test:
                self._r12b0 = r12b0
                return 'PCF8523'
                
            return 'UNKNOWN'

    def __init__(self, i2c_bus):
        # identify the clock chip and set it up
        try:
            self.chip = Clock.Chip(i2c_bus).identify()(i2c_bus)
            if 'square_wave_frequency' not in dir(self.chip):
                log.message("Incompatible version of {}".format(self.chip.__module__))
                raise SystemExit
            # ensure the clock is running
            if self.chip.disable_oscillator:
                self.chip.disable_oscillator = False
                log.message("{} oscillator started".format(self.chip.__class__.__name__))
            self.chip.square_wave_frequency = 1
        except ValueError as e:
            log.message("RTC not available:  '{}'".format(e))
            raise SystemExit
        
        # find the pin attached to the chip's square wave output
        # and set it up for use
        self.setup_sqw()

    # Identify which of the pins (A0, A1, A2, A3, or A4) is connected to the
    # clock chip's square wave output
    def setup_sqw(self):
        # wait a bit for the clock to get going
        time.sleep(1)
        self.sqw = None
        for pin in ['A1', 'A2', 'A3', 'A4', 'A0']:
            board_pin = eval('board.' + pin)
            sqw = digitalio.DigitalInOut(board_pin)
            sqw.direction = digitalio.Direction.INPUT
            sqw.pull = digitalio.Pull.UP
            if Clock.has_square_wave(sqw):
                self.sqw = sqw
                log.message("Square Wave detected on pin {}".format(pin))
                break
            else:
                sqw.deinit()
                
        if self.sqw is None:
            log.message("Square Wave not found on A0, A1, A2, A3 or A4")
            sys.exit()
            
    @staticmethod
    def has_square_wave(sqw):
        end_time = time.monotonic_ns() + 2 * (10**9)
        sqw_val = sqw.value
        while time.monotonic_ns() < end_time:
            if sqw.value != sqw_val:
                break
        return time.monotonic_ns() < end_time

    @property
    def datetime_at_second_boundary(self):
        """Gets the current data and time immediately after the seconds change"""
        dt = self.chip.datetime
        sec = dt[5]
        while True:
            dt = self.chip.datetime
            if dt[5] != sec:
                break
        return dt
        
    # update the time/date stored in the clock_chip
    def update_chip(self, val):
        try:
            if isinstance(val, int):
                # This path is updating the current time by incrementing or
                # or decrementing the time by a second, a minute or an hour.
                
                # When attempting to change only part of the date/time data
                # (as when doing a daylight savings update) the update 
                # should be made immediately after the clock chip has
                # updated itself (ie. the seconds have just changed.)
                # This is because when the time registers are written, the 
                # countdown timer (that determines when the next update
                # occurs) is reset.  So on average, the clock loses 1/2
                # second when the update is done randomly.  Doing the
                # update immediately after the seconds change minimizes
                # this loss.
                # (this is true for both the DS1307 and DS3231)
                secs = time.mktime(self.datetime_at_second_boundary)
                self.chip.datetime = time.localtime(secs+val)
            elif val == 'nearest':
                # This path is synchronizing the clock with an external
                # time source. So we don't need to wait until just after
                # a second change.  On the other hand we do want a full
                # second to go by after we set the time before it increments
                # the seconds again.  This is automatic on ds1307 and ds3231
                # but the pcf8523 requires us to stop the oscillator 
                dt = self.chip.datetime
                secs = time.mktime(dt)
                sec = dt[5]
                secs -= sec
                if sec > 30:
                    secs += 60
                # important for pcf8523 to make clock reset its timing chain
                # so that it starts on a second boundary
                # ds1307 and ds3231 do this automatically
                self.chip.disable_oscillator = True
                self.chip.datetime = time.localtime(secs)
            else:
                # This path is setting a completely new time, perhaps 
                # synchronizing with an external time source.  As above, 
                # we need to stop the oscillator on the pcf8523
                dt = val.split(' ')
                ymd = dt[0].split('/')
                hms = dt[1].split(':')
                mon = int(ymd[0])
                day = int(ymd[1])
                year = int(ymd[2])
                hour = int(hms[0])
                mn = int(hms[1])
                sec = int(hms[2])
                # important for pcf8523 to make clock reset its timing chain
                # so that it starts on a second boundary
                # ds1307 and ds3231 do this automatically
                self.chip.disable_oscillator = True
                self.chip.datetime = time.struct_time(year, mon, day, hour, mn, sec, 0, -1, -1 )
            return time.mktime(self.chip.datetime)
        except:
            return None
            
log = logger.log
