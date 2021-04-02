import time
from collections import namedtuple

"""
Class to support datetime and mktime functions using 1/1/2000 0:0:0
as the basis for time.  1/1/2000 0:0:0 corresponds to time 0.

Time2000.mktime(ts) takes a time.struct_time as input
and returns the number of seconds since 1/1/2000 0:0:0

Time2000.datetime(seconds) takes a number of seconds since 1/1/2000 0:0:0
and returns time.struct_time

The standard time.datetime and time.mktime use 1/1/1970 0:0:0 as the
time basis.  On CircuitPython these functions restrict dates/times to
the range from 1/1/2000 through 1/19/2038

This Time2000 class will correctly represent times throughout 
the 21st century.


"""

Seconds_per_minute =       60
Seconds_per_hour =         Seconds_per_minute * 60
Seconds_per_day =          Seconds_per_hour * 24 
Seconds_per_year =         Seconds_per_day * 365
Seconds_per_leap_year =    Seconds_per_year + Seconds_per_day
Seconds_per_quadrennial =  Seconds_per_leap_year + (3 * Seconds_per_year)


class Time2000:
    # cumulative days by month
    cumulative_days =   [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    day_of_week_magic = [6,  2,  1,  4,   6,   2,   4,   0,   3,   5,   1,   3]   
    # if using the universally accurate formula (see below) use this line here:
    # day_of_week_magic = [0,  3,  2,  5,   0,   3,   5,   1,   4,   6,   2,   4] 
            
    @staticmethod
    def day_of_week(year, month, day):
        """ calculate the day of the week given the year, month and day.
            This formula is correct until the next year that is divisible
            by 4 but is not a leap year.  That doesn't happen until 2100 """
        year -= month < 3
	# to make this universally accurate (not just in the 21st century) use
	# return (year + int(year/4) - int(year/100) + int(year/400) + t[month-1] + day) % 7
        return (year + int(year/4) + Time2000.day_of_week_magic[month-1] + day) % 7
    
    @staticmethod
    def _seconds_before_today(yr, mon, day):
        """ compute seconds from 1/1/2000 until the start of this day """
        return (((yr * 365) + int(yr/4) + ((yr%4) > 0)) +             # days in past years   
	                                                              # 365 days/year + 1 day/quadrennial 
								      # + 1 day if in year 2,3, or 4 of current quadrennial
                Time2000.cumulative_days[mon-1] +                     # days in past months
                (day - 1) +                                           # days in this month
                ((mon > 2) and ((yr%4) == 0))) * Seconds_per_day      # leap day this year    all converted to seconds
    
    @staticmethod
    def mktime(ts):
        """ compute seconds from 1/1/2000 until now given a time.struct_time """
	yr = ts.tm_year % 100
        
        return Time2000._seconds_before_today(yr, ts.tm_mon, ts.tm_mday) + \
                                (ts.tm_hour * Seconds_per_hour) + \
                                (ts.tm_min * Seconds_per_minute) + \
                                ts.tm_sec
        
    class Seconds:
	""" class to simplify dividing seconds into a larger unit and 
	keeping the remainder """
	def __init__(self, secs):
	    self.secs = secs
	
	def __floordiv__(self, divisor):
	    """ implement division with remainder """
	    val = self.secs
	    self.secs = val % divisor
	    return val // divisor
	
	def __ge__(self, secs):
	    """ >= comparison for Seconds """
	    return self.secs >= secs
	        
	@property
	def now(self):
	    """ return the remaining seconds"""
	    return self.secs
	    
	@now.setter
	def now(self, value):
	    """ set the remaining seconds"""
	    self.secs = value
    
    @staticmethod
    def datetime(seconds):
        """ create a time.struct from seconds since 1/1/2000 """
	
	remaining_seconds = Time2000.Seconds(seconds)
	
        # compute current year    
	year = 2000 + 4 * (remaining_seconds // Seconds_per_quadrennial)
	if remaining_seconds >= Seconds_per_leap_year:
        # if seconds.remaining >= Seconds_per_leap_year:
            year += 1
	    remaining_seconds.now -= Seconds_per_leap_year
            leap_year = False
        else:
            leap_year = True
	year += remaining_seconds // Seconds_per_year
        # compute full days in current year
	days = remaining_seconds // Seconds_per_day
        # compute month in current year, and day in current month
        for k, cumulative in enumerate(reversed(Time2000.cumulative_days)):
	    month = 12 - k
	    # if this is leap year, add one to cumulative days for March through December
	    cumulative += (leap_year and (month > 2))
            if days >= cumulative:
                break
        day = days - cumulative + 1
        # compute hour in current day
	hours = remaining_seconds // Seconds_per_hour
        # compute minute in current hour
	minutes = remaining_seconds // Seconds_per_minute
        dayofweek = Time2000.day_of_week(year, month, day)
        
        return time.struct_time((year, month, day, hours, minutes, remaining_seconds.now, dayofweek, days+1, -1))
    
    @staticmethod
    def uptime(secs):
	""" create a uptime_struct from seconds since start """
	
	remaining_seconds = Time2000.Seconds(secs)

	days = remaining_seconds // Seconds_per_day
	hours = remaining_seconds // Seconds_per_hour
	minutes = remaining_seconds // Seconds_per_minute
	
	struct_update = namedtuple('struct_update', ['tm_days', 'tm_hours', 'tm_mins', 'tm_secs'])
	
	return struct_update(days, hours, minutes, remaining_seconds.now)
	
	
