
# Matrix Clock
# Runs on an Adafruit Matrix Portal with 64x32 RGB Matrix display

# Requires secrets.py which identifies the timezone, WiFi SSID and password
# Requires the font file 'IBMPlexMono-Medium-24_jep.bdf'

# secrets.py looks like:
#
# secrets = {
#     'ssid'     : 'your_ssid',
#     'password' : 'your_password',
#     'timezone' : 'America/Chicago'
# }
#
# Timezone names can be found at 'http://worldtimeapi.org/api/timezone'

# Connects to http://worldtimeapi.org/api/timezone/ every 30 minutes to get the correct time

VERSION={"MAJOR": 2, "MINOR": 40}
verstr = '{}.{}'.format(VERSION['MAJOR'], VERSION['MINOR'])

import gc
import time
import board
import busio
import digitalio
import json
import displayio
import neopixel
import microcontroller
import sys
import supervisor
import adafruit_lis3dh
import adafruit_ds3231
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
from rtc import RTC
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix

LOGGING_AVAILABLE = False


# Get wifi details and timezone from the secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise
    

# Setup color constants
def make_rgb_color(color):
    val = 0
    for i in color:
        val = (val * 256) + i
    return val

# Colors are tuples with a red, green and blue components
BRITE_RED   = (90, 0, 0)
BRITE_AMBER = (90, 45, 0)
BRITE_GREEN = (45, 90, 0)

DIM_RED     = (8, 0, 0)
DIM_AMBER   = (16, 8, 0)
DIM_GREEN   = (8, 16, 0)

# RGB colors are integers that combine the R, G and B values
RGB_BRITE_RED = make_rgb_color(BRITE_RED)
RGB_BRITE_AMBER = make_rgb_color(BRITE_AMBER)
RGB_BRITE_GREEN = make_rgb_color(BRITE_GREEN)

RGB_BLACK = 0

RGB_DIM_RED = make_rgb_color(DIM_RED)
RGB_DIM_AMBER = make_rgb_color(DIM_AMBER)
RGB_DIM_GREEN = make_rgb_color(DIM_GREEN)

# Setup a palette for the AM/PM tilegrid
bitmap_palette = displayio.Palette(2)
bitmap_palette[0] = RGB_BLACK
bitmap_palette[1] = RGB_BLACK

# Create bitmap with 'AM' and 'PM'
AM_PM_bitmap = displayio.Bitmap(10, 10, 2)
for x in range(10):
    for y in range(10):
        AM_PM_bitmap[x, y] = 0
A_pixels = ((0,1), (0,2), (0,3), (0,4), (1,0), (1,2), (2,0), (2,2), (3,1), (3,2), (3,3), (3,4))
P_pixels = ((0,5), (0,6), (0,7), (0,8), (0,9), (1,5), (1,7), (2,5), (2,7), (3,5), (3,6), (3,7))
M_pixels = ((5,0), (5,1), (5,2), (5,3), (5,4), (6,1), (7,2), (8,1), (9,0), (9,1), (9,2), (9,3), (9,4))
for x,y in A_pixels:
    AM_PM_bitmap[x, y] = 1
for x,y in P_pixels:
    AM_PM_bitmap[x, y] = 1
for x,y in M_pixels:
    AM_PM_bitmap[x, y] = 1
    AM_PM_bitmap[x, y+5] = 1
    

AM_PM_TileGrid = displayio.TileGrid(AM_PM_bitmap, pixel_shader=bitmap_palette,
                                    width=1, height=1, tile_width=10, tile_height=5)
# Position the AM/PM on the display
AM_PM_TileGrid.x = 48
AM_PM_TileGrid.y = 26

AM_PM_TileGrid[0] = 0


class Button:
    def __init__(self, pin):
        self.button = digitalio.DigitalInOut(pin)
        self.button.direction = digitalio.Direction.INPUT
        self.button.pull = digitalio.Pull.UP
        self.prev_val = True
        self.pressed_start_ns = 0
        
    def read(self):
        pressed = False
        pressed_time = None
        val = self.button.value
        
        if self.prev_val and not val:
            # button just pressed
            pressed = True
            self.pressed_start_ns = time.monotonic_ns()
            
        elif val and not self.prev_val:
            # button just released
            pressed = False
            pressed_time = float(time.monotonic_ns() - self.pressed_start_ns) / (10**9)
            
        elif not val and not self.prev_val:
            # continuing to be pressed
            pressed = True
            pressed_time = float(time.monotonic_ns() - self.pressed_start_ns) / (10**9)
            
        self.prev_val = val
        return (pressed, pressed_time)
        
# # Class to handle the Matrix Portal's buttons
# # Here each button is coded to cycle through a list of options
# class Buttons:

    # class Button:
        # def __init__(self, pin, data):
            # self.button = digitalio.DigitalInOut(pin)
            # self.button.direction = digitalio.Direction.INPUT
            # self.button.pull = digitalio.Pull.UP
            
            # self.data = data
            # self.cycle = 0
            
            # # Set the value of self.cycle that corresponds to the
            # # default settings of color and dim, and blink and center
            # self.set_cycle()
            
            # self.prev_value = True
        
        # # Update this button to match the default options
        # def set_cycle(self):
            # self.cycle = len(self.data) - 1
            # while self.cycle >= 0:
                # vals = self.data[self.cycle]
                # match = True
                # for key, val in vals:
                    # v = options.get(key)
                    # if v != val:
                        # match = False
                # if match:
                    # break
                # self.cycle -= 1
            # if self.cycle < 0:
                # print("Invalid combination of options when setting up button")
        
        # # Update the options object with the options associated with this button
        # def update_options(self):
            # vals = self.data[self.cycle]
            # for key, val in vals:
                # options.replace(key, val)
        
        # # Read the state of the button and detect if pressed since last read    
        # def read(self):
            # pressed = False
            # new_value = self.button.value
            
            # if self.prev_value and not new_value:
                # pressed = True
                # self.cycle += 1
                # if self.cycle >= len(self.data):
                    # self.cycle = 0
                
                # self.update_options()    
                    
            # self.prev_value = new_value
            # return pressed
                    

    # def __init__(self):

        # self.buttons = []
        
        # # The UP button is the color button
        # # data = ((('color', 'track'), ('dim', True)),  \
        # data = ((('color', 'track'), ),               \
                # (('color', 'red'),   ('dim', True)),  \
                # (('color', 'red'),   ('dim', False)), \
                # (('color', 'green'), ('dim', True)),  \
                # (('color', 'green'), ('dim', False)))                
        # self.color_button = Buttons.Button(board.BUTTON_UP, data)
        # self.buttons.append(self.color_button)
        
        # # The DOWN button is the format button
        # data = ((('blink', True),  ('center', True)),  \
                # (('blink', True),  ('center', False)), \
                # (('blink', False), ('center', True)),  \
                # (('blink', False), ('center', False)))        
        # self.format_button = Buttons.Button(board.BUTTON_DOWN, data)
        # self.buttons.append(self.format_button)
            
    # # Read the state of the buttons        
    # def read(self):
        # for button in self.buttons:
            # button.read()

# Class to display and keep track of the time
class TimeKeeper:
    BASEURL = 'http://worldtimeapi.org/api/'
    EXPECTED_ERROR = "Failed to send 3 bytes (sent 0)"
    TEST_RESP = []
    # TEST_RESP = ['{"datetime":"2020-11-01T09:26:34.618465-06:00","dst":true}',
                 # '{"datetime":"2020-11-01T09:30:34.618444-06:00","dst":true}',
                 # '{"datetime":"2020-11-01T08:35:34.618444-06:00","dst":false}',
                 # '{"datetime":"2020-11-01T08:40:34.618444-06:00","dst":false}',
                 # '{"datetime":"2020-11-01T09:45:34.618444-06:00","dst":true}',
                 # '{"datetime":"2020-11-01T09:50:34.618444-06:00","dst":true}']
     
    def __init__(self, tz=None):
        global LOGGING_AVAILABLE
        self.correction_factor = 0
        self.correction_base = 0
        self.prev_hour = 0
        self.prev_minute = 0
        self.show_pending_update = False
        self.internet_correction = False
        self.internet_setup = True
        self.minute_change = False
        self.correction_interval_min = None
        self.accumulated_minutes = None
        self.actual_last_interval = None
        self.correction_armed = False
        self.correction_trigger = False
        self.next_mono_ms = time.monotonic_ns() // (10**6) + 500
        self.blink_colon = True
        self.web_fudge = 2
        self.use_fudgemax = ' '
        self.correction_countdown = 0
        self.wifi_fail_count = 0
        self.unsupported_count = 0
        self.no_sockets_count = 0
        self.memory_allocation_failed_count = 0
        self.socket_object_count = 0
        self.max_wifi_fail = 6
        self.exception_text = None
        self.exception_value = None
        self.last_response_data = None
        self.ds3231 = None
        self.was_dst = None
        self.dst_offset = 0
        self.url = TimeKeeper.BASEURL
        self.last_timezone = None
        self.timezone = None
        self.timezone_change = False
        
        self.local_time_secs = 0

        # self.set_tz(tz)
        self.timezone_change = False
            
        self.failed_to_send_count = 0
        self.waiting_for_SPI_char_count = 0
        
        LOGGING_AVAILABLE = True
        
        # self.log_message("Connecting to   {}".format(secrets["ssid"]))
        # wifi.connect()
        # self.log_esp_info()
        
        self._initialize_ds3231()
        self.sqw = digitalio.DigitalInOut(board.A1)
        self.sqw.direction = digitalio.Direction.INPUT
        
        self._initialize_time()
        
        self.log_message("Version   {}".format(verstr))

        # # initial interval five minutes to get a correction factor
        # self.reset_interval(new_interval=options.get('interval'), one_time_interval=5)
    
    # setup the timezone 
    #  values of tz parameter can be:  None, 'secrets', or a timezone string; like 'America/Chicago'  
    #  None implies using the ip address (of the ISP modem) to determine the location  
    def set_tz(self, tz):
        self.timezone = tz
        if tz == 'secrets':
            if tz in secrets:
                self.timezone = secrets['timezone']
            else:
                # not in secrets, change to use IP address
                self.timezone = None
                
        if self.timezone is None:        
            self.url = TimeKeeper.BASEURL + 'ip'
        else:
            self.url = TimeKeeper.BASEURL + 'timezone/' + self.timezone
            
        self.timezone_change = True
        
    # fudge is the time correction for web turnaround time
    @property
    def fudge(self):
        return self.web_fudge
        
    @fudge.setter
    def fudge(self, val):
        self.web_fudge = val
        self.use_fudgemax = ' '
        fudgemax = options.get('fudgemax')
        if self.web_fudge > fudgemax:
            self.web_fudge = fudgemax
            self.use_fudgemax = '*'

    # Log WiFi requests to wifi_log.txt on the CIRCUITPY filesystem
    def log_message(self, text, do_print=True, add_time=True, traceback=False):
        global LOGGING_AVAILABLE
        if add_time:
            text = "{} {} - {}".format(self.get_formatted_date(), self.get_formatted_time(), text)
        else:
            text = "                    - {}".format(text)
        if do_print:
            print(text)
            if traceback:
                sys.print_exception(self.exception_value)
        if LOGGING_AVAILABLE and options.get('logging'):
            try:
                try:
                    with open("/wifi_log.txt", "a") as wf:
                        wf.write(text + "\n")
                        if traceback:
                            sys.print_exception(self.exception_value, wf)
                        wf.flush()
                except OSError as e:
                    err_code = e.args[0]
                    LOGGING_AVAILABLE = False
                    options.replace('logging', False)
                    if err_code == 28:
                        self.log_message("Filesystem is full - logging disabled")
                    elif err_code == 30:
                        self.log_message("Filesystem is read-only - logging disabled")
                    else:
                        self.log_message("Logging got OSError ({}) - logging disabled".format(err_code))
            except:
                LOGGING_AVAILABLE = False
                options.replace('logging', False)
                self.log_message("Unexpected exception while logging - logging disabled")

    # Initialize ds3231 if available
    def _initialize_ds3231(self):
        # Check for ds3231 RTC
        detected = False
        while not i2c.try_lock():
            pass
        for x in i2c.scan():
            if x == 0x68:
                # self.log_message("ds3231 RTC detected")
                detected = True
                break
        i2c.unlock()
        if detected:
            self.ds3231 = adafruit_ds3231.DS3231(i2c)
            self.ds3231.set_1Hz_SQW()
        else:
            self.log_message("ds3231 RTC not found")
            exit()
        
    # Format ds3231 data
    def format_ds3231(self):
        if self.ds3231:
            dsts = self.ds3231.datetime
            # inttime = self.get_corrected_time_sec(time.time())
            dstime = time.mktime(dsts)
            # delta = dstime - inttime
            return "{} {}  (power lost {}) (SQW mode {})".format(self.get_formatted_date(dstime), self.get_formatted_time(dstime), self.ds3231.power_lost, not self.ds3231.int_sqw)
        return "Not Available"

    def update_ds3231(self, val):
        if self.ds3231:
            try:
                dt = val.split(' ')
                ymd = dt[0].split('/')
                hms = dt[1].split(':')
                mon = int(ymd[0])
                day = int(ymd[1])
                year = int(ymd[2])
                hour = int(hms[0])
                mn = int(hms[1])
                sec = int(hms[2])
                self.ds3231.datetime = time.struct_time(year, mon, day, hour, mn, sec, 0, -1, -1 )
            except:
                return "Invalid date/time"
        return None

    def log_esp_info(self):
        self.log_message("Connected to   {}    Signal strength: {} dBm".format(esp.ssid.decode(), esp.rssi))
        self.log_message("ESP Firmware:  {}".format(esp.firmware_version.decode()))
        self.log_message("ESP Status:    {}".format(esp.status))
        ma = esp.MAC_address
        self.log_message("ESP MAC addr:  {:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}".format(ma[5], ma[4], ma[3], ma[2], ma[1], ma[0]))        
        bs = esp.bssid
        self.log_message("bssid:         {:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}".format(bs[5], bs[4], bs[3], bs[2], bs[1], bs[0]))
        nd = esp.network_data
        self.log_message("IP:            {}".format(esp.pretty_ip(nd['ip_addr'])))
        self.log_message("gateway:       {}".format(esp.pretty_ip(nd['gateway'])))
        self.log_message("netmask:       {}".format(esp.pretty_ip(nd['netmask'])))

    def _initialize_time(self):
        dsts = self.ds3231.datetime
        self.local_time_secs = time.mktime(dsts)

    # # Initialize the internal clock from the internet   
    # def _initialize_time(self):
        # new_time = None
        # init_count = 0
        # while new_time is None and init_count < 5:
            # new_time = self._get_internet_time()
            # if new_time is None:
                # init_count += 1
                # time.sleep(1)

        # if new_time != None:
            # RTC().datetime = time.localtime(new_time)
        # self.correction_base = time.time()
        # self.correction_factor = 0
        # self._update_monotonic_ms()
    
    # Get the time from the internet   
    def _get_internet_time(self):
        new_time = None
        self.exception_text = None
        self.last_response_data = None
        try:
            full_json = None
            try:
                time1 = time.time()
                self.last_response_data = TimeKeeper.TEST_RESP.pop(0)
                time2 = time.time()
            except:
                pass
            if not self.last_response_data:
                time1 = time.time()
                response = wifi.get(self.url)
                time2 = time.time()
                response.drop_connection_when_closed = True
                self.last_response_data = response.text
                response.close()
                response = None
            full_json = json.loads(self.last_response_data)
            time_struct = self._parse_time(full_json["datetime"], full_json["dst"])
            self.timezone = full_json["timezone"]
            self.last_timezone = self.timezone
            new_time = time.mktime(time_struct)
            time3 = time.time()
            fudge = int(round((time3 - time2) + ((2/3) * (time2 - time1))))
            self.fudge = fudge
            new_time += fudge
        except Exception as e:
            self.exception_value = e
            self.exception_text = str(e)
            
        return new_time
        
    # Correct the internal time using a previously computed
    # correction factor.  Return the corrected EPOCH time
    def get_corrected_time_sec(self, cur_time):
        delta_time = cur_time - self.correction_base
        return cur_time + int(round(delta_time * self.correction_factor))

    def get_formatted_time(self, timeis=None):
        if not timeis:
            timeis = self.local_time_secs
            # timeis = self.get_corrected_time_sec(time.time())
        ts = time.localtime(timeis)
        fmt = "{:2d}:{:02d}:{:02d}".format(ts.tm_hour, ts.tm_min, ts.tm_sec)
        return fmt

    def get_formatted_date(self, timeis=None):
        if not timeis:
            timeis = self.local_time_secs
            # timeis = self.get_corrected_time_sec(time.time())
        ts = time.localtime(timeis)
        fmt = "{:2d}/{:02d}/{}".format(ts.tm_mon, ts.tm_mday, ts.tm_year)
        return fmt
        
    # Calculate a correction factor to be used to correct
    # the internal clock until the next correction from the internet
    def _calculate_correction(self, new_time, old_time):
        self.correction_base = new_time
        if self.timezone_change:
            self.timezone_change = False
            self.log_message("Time Zone changed, correction factor remains: {}".format(self.correction_factor))
        else:
            difference = new_time - old_time + self.dst_offset
            self.correction_factor = difference / (self.actual_last_interval * 60)
            self.log_message("Calculated correction from last {} minutes: {:+d} seconds, factor: {}".format(self.actual_last_interval, difference, self.correction_factor))

    # Correct the internal clock from the internet
    # and compute the on-going correction factor
    def correct_from_internet(self):
        self.show_pending_update = True
        self.update_display()
        new_time = self._get_internet_time()
        
        if new_time is not None:
            old_time = time.time()
            RTC().datetime = time.localtime(new_time)
            self._calculate_correction(new_time, old_time)
            self.internet_correction = True
            self._update_monotonic_ms()       
            self.reset_interval()     
            self.wifi_fail_count = 0
        else:
            self.wifi_fail_count += 1
            do_traceback = False
            if 'memory allocation failed' in self.exception_text:
                self.log_message("Memory Allocattion failed - available {}".format(gc.mem_free()))
                self.memory_allocation_failed_count += 1
                if self.memory_allocation_failed_count <= 1:
                    do_traceback = True
            if 'socket object' in self.exception_text:
                self.socket_object_count += 1
                if self.socket_object_count <= 1:
                    do_traceback = True
                elif self.socket_object_count > 3:
                    supervisor.reload()
            if self.exception_text == "Timed out waiting for SPI char":
                self.waiting_for_SPI_char_count += 1
                if self.waiting_for_SPI_char_count <= 1:
                    do_traceback = True
            if self.exception_text == "unsupported types for __gt__: 'NoneType', 'int'":
                self.unsupported_count += 1
                if self.unsupported_count <= 1:
                    do_traceback = True
            if self.exception_text == "No sockets available":
                self.no_sockets_count += 1
                if self.no_sockets_count <= 1:
                    do_traceback = True
            if self.exception_text == "syntax error in JSON":
                if 'application-error.html' not in self.last_response_data:
                    do_traceback = True
                
            if self.exception_text == "datetime":
                # we got a response, but it wasn't what we expected and json raised this exception
                # it could be an 'application error' page from worldtimeapi
                # or it could be a bad time zone specified
                try:
                    full_json = json.loads(self.last_response_data)
                    err = full_json['error']
                    if err == 'unknown location':
                        # must be a bad timezone specification
                        # lets set the timezone to None, so we will use the 'ip' interface
                        print("Bad timezone - Resetting timezone to last valid")
                        options.replace('timezone', self.last_timezone)
                        self.wifi_fail_count = 0
                        return
                except:
                    pass
                
            self.log_message("Request to {} failed ({})".format(self.url, self.wifi_fail_count))
            self.log_message("Exception text: {}".format(self.exception_text), traceback=do_traceback)
            
            if self.exception_text == 'syntax error in JSON':
                # This could be a problem at the server
                # lets try again in five minutes
                if 'application-error.html' in self.last_response_data:
                    self.last_response_data = "Server application error - retry in 5 minutes"
                self.reset_interval(one_time_interval=5)
#                return
                
            if self.exception_text == "No sockets available":
                # force reset now
                self.wifi_fail_count = self.max_wifi_fail
            
            if self.last_response_data:
                self.log_message("Last response: {}".format(self.last_response_data))
                
            if self.wifi_fail_count >= self.max_wifi_fail:
                self.log_message("Resetting the ESP32")
                wifi.reset()
                self.log_message("Reconnecting to {}".format(secrets["ssid"]))
                wifi.connect()

                self.log_esp_info()

                self.wifi_fail_count = 0
                # wait a minute before trying again
                self.reset_interval(one_time_interval=1)

    def reset_interval(self, *, new_interval=None, one_time_interval=None):
        if new_interval:
            self.correction_interval_min = new_interval
            
        if one_time_interval:
            self.accumulated_minutes = one_time_interval
            self.actual_last_interval = one_time_interval
        else:
            self.accumulated_minutes = self.correction_interval_min
            self.actual_last_interval = self.correction_interval_min
        self.correction_armed = False
        self.correction_trigger = False
    
    def _update_monotonic_ms(self): 
        self.base_mono_ms = time.monotonic_ns() // (10**6)
        self.next_mono_ms = self.base_mono_ms + 500 + int(round(500 * self.correction_factor))
    
    @property    
    def time_for_display_update(self):
        current_mono_ms = time.monotonic_ns() // (10**6)
        delta = current_mono_ms - self.base_mono_ms
        corrected_mono_ms = current_mono_ms + int(round(delta * self.correction_factor))
        if corrected_mono_ms >= self.next_mono_ms:
            # set so another update occurs 500 ms from now
            self.next_mono_ms += 500 + int(round(500 * self.correction_factor))
            # indicate to update the display
            return True
        return False

    @property
    def time_for_correction(self):
        return self.correction_trigger or self.timezone_change
        
    @property
    def minute_changed(self):
        change = self.minute_change
        self.minute_change = False
        return change

    def _parse_time(self, timestring, is_dst=-1):
        """ Given a string of the format YYYY-MM-DDTHH:MM:SS.SS-HH:MM (and
            optionally a DST flag), convert to and return an equivalent
            time.struct_time 
        """
        if self.was_dst and not is_dst:
            # end of daylight time
            self.dst_offset = 3600
        elif is_dst and not self.was_dst:
            # start of daylight time
            self.dst_offset = -3600
        else:
            self.dst_offset = 0
        self.was_dst = is_dst
        
        date_time = timestring.split('T')         # Separate into date and time
        year_month_day = date_time[0].split('-')  # Separate time into Y/M/D
        hour_minute_second = date_time[1].split('+')[0].split('-')[0].split(':')
        
        return time.struct_time(int(year_month_day[0]),
                                int(year_month_day[1]),
                                int(year_month_day[2]),
                                int(hour_minute_second[0]),
                                int(hour_minute_second[1]),
                                int(hour_minute_second[2].split('.')[0]),
                                -1, -1, is_dst)

    # Update the time display
    def update_display(self):
    
        # now = time.localtime(self.get_corrected_time_sec(time.time()))
        now = time.localtime(self.local_time_secs)
    
        hours = now[3]
        minutes = now[4]

        # Determine the display color
        color_option = options.get_actual_color()
        if isinstance(color_option, tuple):
            if hours >= options.get('night') or hours < options.get('day'):
                color_option = color_option[0]
            else:
                color_option = color_option[1]
            
        hour_label.color = color_option
        min_label.color = color_option
    
        if self.show_pending_update:
            colon_label.color = RGB_DIM_AMBER
        else:
            colon_label.color = color_option

        # Handle AM/PM
        show_ampm = options.get('ampm')
        if not show_ampm:
            color_option = RGB_BLACK
        # 12 or 24 hour display
        if not options.get('24h'):
            bitmap_palette[1] = color_option
            if hours >= 12: # PM
                AM_PM_TileGrid[0] = 1
                hours -= 12
            else:           # AM
                AM_PM_TileGrid[0] = 0
            if hours == 0:
                hours = 12
        else:
            show_ampm = False
            bitmap_palette[1] = RGB_BLACK

        # if self.internet_setup:
            # self.log_message("Clock set to:         {:2d}:{:02d},  fudge factor = {:+d}{}".format(hours, minutes, self.web_fudge, self.use_fudgemax))
            # self.internet_setup = False
    
        # if self.internet_correction:
            
            # self.log_message("Internet Correction:  {:2d}:{:02d} --> {:2d}:{:02d},  fudge factor = {:+d}{}  ds3231: {}, free memory {}".format(self.prev_hour, self.prev_minute, hours, minutes, self.web_fudge, self.use_fudgemax, self.format_ds3231(), gc.mem_free()))
            # self.internet_correction = False
            # self.show_pending_update = False
    
        # if (hours == self.prev_hour and minutes == (self.prev_minute - 1)) or \
           # (hours == (self.prev_hour - 1) and minutes == 59 and self.prev_minute == 0) or \
           # (hours == 12 and self.prev_hour == 1 and minutes == 59 and self.prev_minute == 0) or \
           # (hours == 23 and self.prev_hour == 0 and minutes == 59 and self.prev_minute == 0):
            # self.log_message("Clock went backward!")
            # self.log_message("           Previous  {}:{:02d}".format(self.prev_hour, self.prev_minute), add_time=False)
            # self.log_message("           Now       {}:{:02d}".format(hours, minutes), add_time=False)
            
        # if self.correction_armed:
            # self.correction_countdown -= 1
            # if self.correction_countdown <= 0:
                # self.correction_trigger = True
        
        # When the correction interval has expired, set 'armed' and 
        # setup a counter to wait 30 seconds before 'triggering' the
        # correction    
        # if self.prev_minute != minutes:
            # self.minute_change = True
            # self.accumulated_minutes -= 1
            # if self.accumulated_minutes <= 0 and not self.correction_armed:
                # self.correction_armed = True
                # self.correction_countdown = 60
        # else:
            # self.minute_change = False
    
        # self.prev_hour = hours
        # self.prev_minute = minutes
    
        blink = options.get('blink')
        center = options.get('center')
        
        colon = ":"
        if blink and not self.show_pending_update:
            # self.blink_colon = not self.blink_colon
            # if self.blink_colon:
            if self.sqw.value:
                colon = " "
    
        hour_label.text = "{}".format(hours)
        min_label.text = "{:02d}".format(minutes)
        colon_label.text = colon
    
        if center and hours < 10:
            hour_label.x = 6
            min_label.x = 29
            colon_label.x = 21
        else:
            if hours < 10:
                hour_label.x = 13
            else:
                hour_label.x = 0
            min_label.x = 36
            colon_label.x = 28
    
        y_offset = -2 if show_ampm else 0
        hour_label.y = 16 + y_offset
        min_label.y = 16 + y_offset
        colon_label.y = 14 + y_offset
        
        matrix.display.show(group)

class Command:
    def __init__(self, opts):
        self.options = opts
    
    def run(self, cmdstr):
        key = cmdstr[0]
        parm = ' '.join(cmdstr[1:])
        try:
            # Lookup command name in dictionary
            cmd = self.options.commands[key]
        except:
            print("Invalid command")
            return False
        
        # check for valid parameter type
        for t in cmd[0]:
            try:
                valid, val = t(parm)
            except:
                print("No parameter")
                return False
            # if parameter type is valid, execute the command
            if valid:
                cmd[2](self.options, key, val)
                break
        if not valid:
            print("Invalid parameter")
        return valid

    # valid hour is int, between 0 and 23
    def testHour(val):
        valid, v = Command.testInt(val)
        if valid:
            if (v >= 0) and (v <= 23):
                return (True, v)
        return (False, None)
    
    # any string is valid, including null string
    def testStr(val):
        return (True, val)

    # valid bool is true or false or null which is true
    def testBool(val):
        if val == '':
            return (True, True)
        for v in ('true', 'enable', 'enabled', 'yes', 'on'):
            if val == v:
                return (True, True)
        for v in ('false', 'disable', 'disabled', 'no', 'off'):
            if val == v:
                return (True, False)
        return (False, None)
    
    # valid None is none
    def testNone(val):
        if val == 'none':
            return (True, None)
        return (False, None)
    
    # validate integer
    def testInt(val):
        try:
            v = int(val)
            return (True, v)
        except:
            return (False, None)
    
    # validate color        
    def testColor(val):
        for v in ('red', 'green', 'track'):
            if val == v:
                return (True, val)
        return (False, None)
    
    # validate rotation parameter    
    def testRotate(val):
        valid, v = Command.testInt(val)
        if valid:
            if v == 0 or v == 180:
                return (True, v)
        elif val == 'auto':
            return (True, val)
            
        return (False, None)

    # validate timezone parameter
    def testTimezone(val):
        if val == 'secrets':
            try:
                _ = secrets['timezone']
                return (True, val)
            except:
                return (False, None)
        if val is '' or val == 'none':
            return (True, None)
        return (True, val)
        
    
class Options:
    DEFAULT_FILE = 'defaults.json'
    
    def __init__(self, cmds):
        self.commands = cmds
    
    # get an option by key    
    def get(self, key):
        return self.commands[key][1]
    
    # get actual (RGB) color based on 'color' option    
    def get_actual_color(self):
        item = self.commands['color']
        color = item[1]
        item = self.commands['dim']
        dim = item[1]
        if color == 'track':
            if dim:
                return (RGB_DIM_RED, RGB_DIM_GREEN)
            return (RGB_DIM_RED, RGB_BRITE_GREEN)
        if dim:
            if color == 'red':
                return RGB_DIM_RED
            return RGB_DIM_GREEN
        if color == 'red':
            return RGB_BRITE_RED
        return RGB_BRITE_GREEN

    # Replace an option's value
    def replace(self, key, val, show=True):
        # if key == 'ds3231':
            # print("Options.replace called with key=ds3231")
            # alternate = time_keeper.update_ds3231(val)
        # else:
        if key != 'logging' or val is False or LOGGING_AVAILABLE:
            item = self.commands[key]
            item[1] = val
            self.commands[key] = item
        
        if key == 'interval':
            if 'time_keeper' in globals():
                time_keeper.reset_interval(new_interval=val)
                
        if key == 'timezone':
            if 'time_keeper' in globals():
                time_keeper.set_tz(val)
        
        if key == 'rotation':
            self.set_rotation(val)    
            
        if show:
            self.show('show', key)

    def set_rotation(self, val):
        if isinstance(val, str):
            # must be auto
            # Use the accelerameter to determine the display's orientation
            _, y, _ = lis3dh.acceleration
            if y > 0:
                val = 0
            else:
                val = 180
        matrix.display.rotation = val

    def ds3231(self, key, val, show=True):
        alternate = None
        if val == 'set':
            cur_time = time_keeper.get_corrected_time_sec(time.time())
            time_keeper.ds3231.datetime = time.localtime(cur_time)
        elif val:
            alternate = time_keeper.update_ds3231(val)
        if show:
            self.show('show', 'ds3231', alt_text=alternate)
            
    def nearest(self, key, val, show=False):
        # adjust time to nearest minute
        dt = time_keeper.ds3231.datetime
        secs = time.mktime(dt)
        sec = dt[5]
        secs -= sec
        if sec > 30:
            secs += 60
        time_keeper.ds3231.datetime = time.localtime(secs)
        time_keeper.local_time_secs = secs
            
    def save(self, key, fname, show=True):
        if not fname:
            fname = Options.DEFAULT_FILE
        if len(fname.split('.')) == 1:
            fname += '.json'
        optdic = {}
        for key, value in self.commands.items():
            if value[3]:
                optdic[key] = value[1]
        
        try:
            with open(fname, 'w') as options_file:
                json.dump(optdic, options_file)
            print("Options saved to {}".format(fname))
        except Exception as e:
            print("Exception saving options to {}".format(fname))
            txt = str(e).split(']')
            if len(txt) > 1:
                txt = txt[1]
            else:
                txt = txt[0]
            print(txt)
            
    def restore(self, key, fname, show=True):
        if not fname:
            fname = Options.DEFAULT_FILE
        if len(fname.split('.')) == 1:
            fname += '.json'
        try:
            with open(fname) as options_file:
                optdic = json.load(options_file)
            
            for key, value in optdic.items():
                self.replace(key, value, show=False)
            print("Options restored from {}".format(fname))
        except Exception as e:
            print("Exception loading options from {}".format(fname))
            txt = str(e).split(']')
            if len(txt) > 1:
                txt = txt[1]
            else:
                txt = txt[0]
            print(txt)

    # Show an option by key, or all options
    def show(self, cc, key, alt_text=None):
        if cc != 'show':
            key = cc
        if key == '':
            # show all options
            for key, item in options.commands.items():
                self.show_item(key, item, alt_text)
        else:
            # show single option
            try:
                item = self.commands[key]
                self.show_item(key, item, alt_text)
            except:
                print("Invalid Option")

    def show_item(self, key, item, alt_text):
        if item[4]:
            if alt_text:
                val = alt_text
            elif key == 'ds3231':
                val = time_keeper.format_ds3231()
            elif key == 'memory':
                val = gc.mem_free()
            elif key == 'time':
                val = '{} {}'.format(time_keeper.get_formatted_date(), time_keeper.get_formatted_time())
            else:
                val = item[1]
                if key == 'timezone':
                    tz = None
                    if val == 'secrets' and 'timezone' in secrets:
                        tz = secrets['timezone']
                    if val is None and time_keeper.timezone:
                        tz = time_keeper.timezone
                    if tz:
                        val = '{} ({})'.format(val, tz)
            print('{:9s} is {}'.format(key, val))

class Console:
    def __init__(self):
        self.inbuffer = ''
        
    def get_command(self):
        cmdstr = None
        while supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            
            # handle backspace
            if ch[0] == '\x7f':
                if len(self.inbuffer) > 0:
                    self.inbuffer = self.inbuffer[:-1]
                    print()
                    print("{}".format(self.inbuffer), end='')
                    
            # handle newline
            elif ch[0] == '\n':
                print('')
                if self.inbuffer != '':
                    cmdstr = self.inbuffer.split()
                    if len(cmdstr) == 1:
                        cmdstr.append('')
                self.inbuffer = ''
                
            # handle normal characters
            else:
                self.inbuffer += ch
                print("{}".format(ch), end='')
        return cmdstr        
        
class Timer:
    def __init__(self):
        self.start_time = None
        self.time = None
    
    @property
    def start(self):
        self.start_time = time.monotonic_ns()
        self.time = None
        return self.start_time
        
    @property
    def stop(self):
        if self.start_time:
            self.time = time.monotonic_ns() - self.start_time
        self.start_time = None
        return self.time
        
# # --- Network setup ---
# esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
# esp32_ready = digitalio.DigitalInOut(board.ESP_BUSY)
# esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
# spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
# esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
# wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, None, attempts=4, debug=False)

# Turn off the status neopixel
#     The neopixel is WAY too bright for a clock in a dark room
neoled = neopixel.NeoPixel(board.NEOPIXEL, 1)
neoled.brightness = 0.05
neoled.fill((0, 0, 0))

# --- displayio setup ---
matrix = Matrix(bit_depth=5)    # bit_depth=5 allows 32 levels for each of R, G, and B
                                # and this allows maximum dimming of the display

font = bitmap_font.load_font("/IBMPlexMono-Medium-24_jep.bdf")
font.load_glyphs('0123456789:')

hour_label = Label(font, max_glyphs=2)
min_label = Label(font, max_glyphs=2)
colon_label = Label(font, max_glyphs=1)

group = displayio.Group(max_size=4)
group.append(colon_label)
group.append(hour_label)
group.append(min_label)
group.append(AM_PM_TileGrid)

matrix.display.show(group)
        
# setup the accelerameter for later use
i2c = busio.I2C(board.SCL, board.SDA)
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
_ = lis3dh.acceleration
time.sleep(0.1)
        
# --- Options setup   option        validation                         value      function         saveable  display
options = Options( {'interval' : [(Command.testInt,),                  30,       Options.replace,  True,     True],
                    'ping' :     [(Command.testNone, Command.testStr), None,     Options.replace,  True,     True],
                    '24h' :      [(Command.testBool,),                 False,    Options.replace,  True,     True],
                    'blink' :    [(Command.testBool,),                 True,     Options.replace,  True,     True],
                    'center' :   [(Command.testBool,),                 True,     Options.replace,  True,     True],
                    'dim' :      [(Command.testBool,),                 True,     Options.replace,  True,     True],
                    'ampm':      [(Command.testBool,),                 True,     Options.replace,  True,     True],
                    'color' :    [(Command.testColor,),                'track',  Options.replace,  True,     True],
                    'night' :    [(Command.testHour,),                 22,       Options.replace,  True,     True],
                    'day' :      [(Command.testHour,),                 6,        Options.replace,  True,     True],
                    'logging' :  [(Command.testBool,),                 True,     Options.replace,  True,     True],
                    'collect' :  [(Command.testBool,),                 False,    Options.replace,  True,     True],
                    'fudgemax' : [(Command.testInt,),                  10,       Options.replace,  True,     True],
                    'rotation' : [(Command.testRotate,),               'auto',   Options.replace,  True,     True],
                    'timezone' : [(Command.testTimezone,),             None,     Options.replace,  True,     True],
                    'ds3231' :   [(Command.testStr,),                  None,     Options.ds3231,   False,    True],
                    'version' :  [(Command.testStr,),                  verstr,   Options.show,     False,    True],
                    'memory' :   [(Command.testStr,),                  None,     Options.show,     False,    True],
                    'time' :     [(Command.testStr,),                  None,     Options.show,     False,    True],
                    'nearest':   [(Command.testStr,),                  None,     Options.nearest,  False,    False],
                    'save' :     [(Command.testStr,),                  None,     Options.save,     False,    False],
                    'restore' :  [(Command.testStr,),                  None,     Options.restore,  False,    False],
                    'show' :     [(Command.testStr,),                  None,     Options.show,     False,    False]} )

options.set_rotation(options.get('rotation'))
options.replace('timezone', 'secrets', show=False)
       
options.restore('restore', Options.DEFAULT_FILE)

command = Command(options)

# # Setup the buttons
up_button = Button(board.BUTTON_UP)
down_button = Button(board.BUTTON_DOWN)

# Create the time_keeper 
time_keeper = TimeKeeper(tz=options.get('timezone'))

# Create the console
console = Console()

# Loop forever, get commands, check buttons, and update the display
keep_going = True
inpbuffer = ''
last_sqw = False
timer = Timer()
while keep_going:

    try:
        # Check for and execute a command from the console
        timer.start
        cmdstr = console.get_command()
        if cmdstr:
            command.run(cmdstr)
                
        # Every 50 ms:
        # Read the buttons
        
        pressed, pressed_time = down_button.read()
        # check if button just released
        if not pressed and pressed_time is not None:
            # button was pressed and released
            if pressed_time > 2.0:
                print("Long press {} seconds".format(pressed_time))
            else:
                # adjust clock to nearest minute
                options.nearest(None, None)
                    
        # Every 1/2 second:
        # Update the display every 1/2 second with
        # time so that when using a blinking
        # cursor, it blinks once per second (1/2 second on,
        # 1/2 second off)
        
        # time_keeper.sqw.value changes every 1/2 second
        sqw = time_keeper.sqw.value
        if sqw != last_sqw:
            last_sqw = sqw
            time_keeper.update_display()
            
            # Once per second, increment the time
            if sqw:
                time_keeper.local_time_secs += 1

        # If we processed some long running operation above,
        #   update the running time (local_time_secs) from the ds3231
        timer.stop
        if timer.time > 300_000_000:
            # update the time from the ds3231
            time_keeper.local_time_secs = time.mktime(time_keeper.ds3231.datetime)
            print("long wait - local_time updated from ds3231")
                    
    except Exception as e:
        try:
            if time_keeper.exception_text:
                time_keeper.log_message("Last exception text: {}".format(time_keeper.exception_text))
            if time_keeper.last_response_data:
                time_keeper.log_message("Last response data:  {}".format(time_keeper.last_response_data))
            time_keeper.log_message(e, add_time=False, traceback=True)
        except:
            pass
            
        supervisor.reload()

    
    time.sleep(0.050)

