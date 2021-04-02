# Matrix Clock

# clock.py encapsulates the handling of the hardware RTC
# it supports ds1307, ds3231 and pcf8523 clocks, and requires
# access to the SQW (Square Wave) outputs.  The SQW pin on
# the clock boards must be wired to one of the available
# pins on the Adafruit Matrix Portal board (A0, A1, A2, A3, A4)

# It will dynamically determine which of these chips is connected
# and load the appropriate driver

from adafruit_register import i2c_bit
from adafruit_register import i2c_bits
from adafruit_bus_device.i2c_device import I2CDevice
import sys
import digitalio
import board
import busio
import time
import rtc
from datetime_2000 import Time2000

import logger

# Identifies which clock chip is available
class Clock:
    
    class Chip:
        _r13b0 = i2c_bit.ROBit(0x13, 0)
        _r3fb0 = i2c_bit.RWBit(0x3f, 0)
        
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
            try:
                r13b0 = self._r13b0
            except OSError:
                dev_id = 'DS3231'
            else:
                try:
                    r3fb0 = self._r3fb0
                    self._r3fb0 = not r3fb0
                    if r3fb0 == self._r3fb0:
                        dev_id = 'PCF8523'
                    else:
                        dev_id = 'DS1307'
                        self._r3fb0 = r3fb0
                except OSError:
                    print("OSError accessing reg 0x3F")
                    
            return dev_id
            
    def __init__(self, i2c_bus):
        # identify the clock chip and set it up
        try:
            self.chip = Clock.Chip(i2c_bus).identify()(i2c_bus)
            self.pcf8523 = True if self.chip.__class__.__name__ == 'PCF8523' else False
            if 'square_wave_frequency' not in dir(type(self.chip)):
                log.message("Incompatible version of {}".format(self.chip.__module__))
                raise SystemExit
            # ensure the clock is running
            if self.chip.disable_oscillator:
                self.chip.disable_oscillator = False
                log.message("{} oscillator started".format(self.chip.__class__.__name__))
                time.sleep(1)
            self.chip.square_wave_frequency = 1
            
            if not self.validate_datetime():
                ts = time.struct_time((2000, 1, 1, 0, 0, 0, -1, -1, -1))
                self.chip.datetime = ts
            
        except ValueError as e:
            log.message("RTC not available:  '{}'".format(e))
            raise SystemExit
        
        # find the pin attached to the chip's square wave output
        # and set it up for use
        self.sqw = self.setup_sqw()
        if self.sqw is None:
            sys.exit()

    def validate_datetime(self):
        """ determine if the date/time stored in the RTC chip
        is valid. """
        ts = self.chip.datetime
        if ts.tm_mday < 1 or ts.tm_mday > 31:
            return False
        if ts.tm_mon < 1 or ts.tm_mon > 12:
            return False
        if ts.tm_hour > 23 or ts.tm_min > 59 or ts.tm_sec > 59:
            return False
        return True

    # Identify which of the pins (A0, A1, A2, A3, or A4) is connected to the
    # clock chip's square wave output
    @staticmethod
    def setup_sqw():
        """ detect which pin has a changing signal and set that  pin
        up as an input with a pullup """
        for pin in ['A1', 'A2', 'A3', 'A4', 'A0']:
            board_pin = eval('board.' + pin)
            sqw = digitalio.DigitalInOut(board_pin)
            sqw.direction = digitalio.Direction.INPUT
            sqw.pull = digitalio.Pull.UP
            if Clock.has_square_wave(sqw):
                log.message("Square Wave detected on pin {}".format(pin))
                break
            else:
                sqw.deinit()
        else:        
            log.message("Square Wave not found on A0, A1, A2, A3 or A4")
            sqw = None
        return sqw
        
    @staticmethod
    def has_square_wave(sqw):
        """ test if a signal is seen on the pin specified """
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
        sec = dt.tm_sec
        while dt.tm_sec == sec:
            dt = self.chip.datetime
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
                # occurs) is reset (on DS1307 and DS3231).  So on average, 
                # the clock loses 1/2 second when the update is done randomly.  
                # Doing the update immediately after the seconds change minimizes
                # this loss.
                secs = Time2000.mktime(self.datetime_at_second_boundary)
                self.chip.datetime = Time2000.datetime(secs+val)
            elif val == 'nearest':
                # This path is synchronizing the clock with an external
                # time source. So we don't need to wait until just after
                # a second change.  On the other hand we do want a full
                # second to go by after we set the time before it increments
                # the seconds again.  This is automatic on ds1307 and ds3231
                # but the pcf8523 requires us to stop the oscillator 
                dt = self.chip.datetime
                secs = Time2000.mktime(dt)
                sec = dt.tm_sec
                secs -= sec
                if sec > 30:
                    secs += 60
                # important for pcf8523 to make clock reset its timing chain
                # so that it starts on a second boundary
                # ds1307 and ds3231 do this automatically
                if self.pcf8523:
                    self.chip.disable_oscillator = True
                self.chip.datetime = Time2000.datetime(secs)
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
                if self.pcf8523:
                    self.chip.disable_oscillator = True
                self.chip.datetime = time.struct_time(year, mon, day, hour, mn, sec, Time2000.day_of_week(year, mon, day), -1, -1 )
            return Time2000.mktime(self.chip.datetime)
        except:
            return None
            
log = logger.log
