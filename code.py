# Matrix Clock

# Runs on an Adafruit Matrix Portal with 64x32 RGB Matrix display
#
# Requires - a RTC chip (ds3231, ds1307 and pcf8523 supported)
# Requires - the Square Wave output pin of the RTC board must be connected
#            to one of the pins of the Matrix Portal (A0, A1, A2, A3, A4)
#            No external pull-up resistor is required
#
# copy the adafruit_ds3231, adafruit_ds1307 or adafruit_pcf8523 modules 
# provided in this repository onto the CIRCUITPY drive in /lib
#
# MatrixClock will identify which chip you have connected and import the
# correct module.  It will also find to which pin you connected the clock
# chip's square wave output.
#

VERSION={"MAJOR": 3, "MINOR": 45}
verstr = '{}.{}'.format(VERSION['MAJOR'], VERSION['MINOR'])

__version__ = verstr+".0-auto.0"
__repo__ = "https://github.com/mikejc58/MatrixClock.git"

import gc
import time
import board
import busio
import digitalio
import json
import displayio
import sys
import supervisor
import microcontroller
import struct
from adafruit_register import i2c_bit
from adafruit_bus_device.i2c_device import I2CDevice
import adafruit_lis3dh
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix

import console
from clock import Clock
import logger   
from datetime_2000 import Time2000
import wifi

def strsplit(txt, splits=' '):
    """ split a string at any of the characters in 'splits', but don't split
        quoted substrings (quoted with single or double quotes) """
    lst = []
    accum = ''
    state = 0
    for ch in txt:
        # state 0: in whitespace
        if state == 0:
            if ch in splits:
                continue
            elif ch == "'":
                state = 2
                accum = "'"
            elif ch == '"':
                state = 3
                accum = '"'
            else:
                state = 1
                accum = ch
        # state 2: inside a quoted substrnig, quoted with single quotes
        elif state == 2:
            accum += ch
            if ch == "'":
                state = 0
                lst.append(accum)
                accum = ''
        # state 3: inside a quoted substring, quoted with double quotes
        elif state == 3:
            accum += ch
            if ch == '"':
                state = 0
                lst.append(accum)
                accum = ''
        # state 1: in a substring
        elif state == 1:
            if ch in splits:
                lst.append(accum)
                state = 0
                accum = ''
            elif ch == '"':
                lst.append(accum)
                state = 3
                accum = '"'
            elif ch == "'":
                lst.append(accum)
                state = 2
                accum = "'"
            else:
                accum += ch
    if accum:
        lst.append(accum)
    return lst
            
class Colors:
    def make_rgb_color(color):
        val = 0
        for i in color:
            val = (val * 256) + i
        return val

    Bright_Red = make_rgb_color((90, 0, 0))
    Bright_Amber = make_rgb_color((90, 45, 0))
    Bright_Green = make_rgb_color((45, 90, 0))
    
    Dim_Red = make_rgb_color((8, 0, 0))
    Dim_Amber = make_rgb_color((16, 8, 0))
    Dim_Green = make_rgb_color((8, 16, 0))
    
    Black = make_rgb_color((0, 0, 0))
    
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

# Class to keep track of the time
class TimeKeeper:    
    
    weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
     
    def __init__(self):
        """ construct the TimeKeeper object """
        self.clock = Clock(i2c)
        self.sync_time()
        self.uptime = 0

    def update_chip(self, val):
        """ update the hardware RTC with a new date/time """
        new_time = self.clock.update_chip(val)
        if new_time is None:
            return "Invalid date/time"
        self.sync_time()
        return None

    def sync_time(self):
        """ synchronize the locallly kept time (based on counting the SQW transitions) 
            with the time from the hardware RTC """
        self.local_time_secs = Time2000.mktime(self.clock.datetime_at_second_boundary)

    # Format clock_chip data
    def format_chip(self, weekday=True):
        """ format the date/time from the hardware RTC for printing """
        return self.get_formatted_date_time(self.clock.chip.datetime, weekday)

    def format_date_time(self, time_secs=None, weekday=True):
        """ format a time (seconds since Jan 1, 2000) for printing """
        if not time_secs:
            time_secs = self.local_time_secs
        return self.get_formatted_date_time(Time2000.datetime(time_secs), weekday)

    def get_formatted_date_time(self, ts, weekday):
        week_str = '  ' + TimeKeeper.weekdays[ts.tm_wday] if weekday else ''
        return "{:2d}/{:02d}/{:4d} {:2d}:{:02d}:{:02d}{}".format(ts.tm_mon, ts.tm_mday, ts.tm_year, ts.tm_hour, ts.tm_min, ts.tm_sec, week_str)
        
class Command:
    def __init__(self, opts):
        self.options = opts
    
    def run(self, cmdstr):
        """ run a command from the serial console, or from a network socket """
        key = cmdstr[0]
        parm = ' '.join(cmdstr[1:])
        try:
            # Lookup command name in dictionary
            cmd = self.options.commands[key]
        except:
            log.print("Invalid command")
            return False
        
        if parm == '?':
            txt = cmd[5]
            log.print("{} valid parameters: {}".format(key, txt))
            return True
        
        # check for valid parameter type
        for t in cmd[0]:
            try:
                valid, val = t(parm)
            except:
                log.print("No parameter")
                return False
            # if parameter type is valid, execute the command
            if valid:
                cmd[2](self.options, key, val)
                break
        if not valid:
            log.print("Invalid parameter")
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
        
    # a pair of strings
    def testPair(val):
        if isinstance(val, str):
            lst = strsplit(val, ' ,:;')
            if len(lst) == 2:
                return (True, (lst[0], lst[1]))
        return (False, None)

    def testNull(val):
        return (val == '' or val is None, val)

    # valid bool is true, enable, enabled, yes, on,
    #               false, disable, disabled, no, off
    def testBool(val):
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
                return (Colors.Dim_Red, Colors.Dim_Green)
            return (Colors.Dim_Red, Colors.Bright_Green)
        if dim:
            if color == 'red':
                return (Colors.Dim_Red, Colors.Dim_Red)
            return (Colors.Dim_Green, Colors.Dim_Green)
        if color == 'red':
            return (Colors.Bright_Red, Colors.Bright_Red)
        return (Colors.Bright_Green, Colors.Bright_Green)

    # Replace an option's value
    def replace(self, key, val, show=True):
        if not isinstance(val, str) or val:
            if key != 'logging' or val is False or log.AVAILABLE:
                item = self.commands[key]
                item[1] = val
                self.commands[key] = item
            
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
        display.matrix.display.rotation = val

    def rtc(self, key, val, show=True):
        alternate = None
        val = val.strip()
        if val:
            # val can be 'sync', 'nearest', '+xxx', '-xxx' (where xxx is sec[ond], min[ute], h[ou]r) or 'mm/dd/yyyy hh:mm:ss'
            if val == 'sync':
                time_keeper.sync_time()
            else:    
                if val[0] == '+' or val[0] == '-':
                    direction = +1 if val[0] == '+' else -1
                    unit = val[1:]
                    if unit == 'sec' or unit == 'second':
                        val = direction
                    elif unit == 'min' or unit == 'minute':
                        val = direction * 60
                    elif unit == 'hr' or unit == 'hour':
                        val = direction * 3600
                    else:
                        alternate = 'Invalid time adjustment'
                
                if alternate is None:
                    alternate = time_keeper.update_chip(val)
                
        if show:
            self.show('show', 'rtc', alt_text=alternate)

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
            log.message("Options saved to {}".format(fname))
        except Exception as e:
            log.message("Exception saving options to {}".format(fname))
            txt = str(e).split(']')
            if len(txt) > 1:
                txt = txt[1]
            else:
                txt = txt[0]
            log.message(txt.strip())

    def restart(self, key, val):
        log.message("Restarting MatrixClock")
        esp_mgr.disconnect_from_socket()
        time_keeper.clock.chip.square_wave_frequency = 0
        time_keeper.clock.sqw.deinit()
        supervisor.reload()
            
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
            log.message("Options restored from {}".format(fname))
        except Exception as e:
            log.message("Exception loading options from {}".format(fname))
            log.message("e = '{}'".format(e))
            txt = str(e).split(']')
            if len(txt) > 1:
                txt = txt[1]
            else:
                txt = txt[0]
            log.message(txt.strip())
    
    def join(self, key, val, show=True):
        ssid = None
        passwd = None
        if val:
            lst = strsplit(val, ' ,:;')
            try:
                ssid = lst[0]
                try:
                    passwd = lst[1]
                except IndexError:
                    log.print("No password specified")
            except IndexError:
                log.print("Invalid ssid '{}'".format(val))
        else:
            ssid, passwd = self.commands['network'][1]
            
        if ssid and passwd:
            if esp_mgr.connect_to_ap(ssid, passwd):
                log.message("Joined with {}".format(ssid))
            else:
                log.message("Join with {} failed".format(ssid))
        else:
            log.print("No network specified")
            
    def connect(self, key, val, show=True):
        if not esp_mgr.ap:
            self.join(None, None)
            
        host = None
        if val:
            lst = strsplit(val, ' ,:;')
            try:
                host = lst[0]
                try:
                    port = lst[1]
                except IndexError:
                    port = '65432'
            except IndexError:
                log.print("Invalid host '{}'".format(val))
        else:
            host, port = self.commands['host'][1]
        
        if host and port:    
            try:
                port = int(port)
            except ValueError:
                log.print("Invalid port '{}'".format(port))
            actual_port = esp_mgr.connect_to_socket(host, port)
            if actual_port:
                log.message("Connected to {}:{}".format(host, actual_port))
            else:
                log.message("Connection to {}:{} failed".format(host, port))
        else:
            log.print("No host:port specified")
 
    def bye(self, key, val, show=False):
        """ disconnect from socket """
        esp_mgr.disconnect_from_socket()

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
                log.print("Invalid Option")

    def show_item(self, key, item, alt_text):
        if item[4]:
            if alt_text:
                val = alt_text
            elif key == 'startup':
                val = str(supervisor.runtime.run_reason).split('.')[2]
            elif key == 'rtc':
                val = time_keeper.format_chip().strip() + '   (' + time_keeper.clock.chip.__class__.__name__ + ')'
            elif key == 'memory':
                val = '{}  byte-order {}  packed {}'.format(gc.mem_free(), sys.byteorder, struct.pack('!BBBB', 127, 0, 0, 1))
            elif key == 'time':
                val = "{}".format(time_keeper.format_date_time()).strip()
            elif key == 'uptime':
                us = Time2000.uptime(time_keeper.uptime)
                val = ''
                comma = ''
                if us.tm_days:
                    plural = 's' if us.tm_days > 1 else ''
                    val += '{} day{}'.format(us.tm_days, plural)
                    comma = ', '
                if us.tm_hours:
                    plural = 's' if us.tm_hours > 1 else ''
                    val += '{}{} hour{}'.format(comma, us.tm_hours, plural)
                    comma = ', '
                if us.tm_mins:
                    plural = 's' if us.tm_mins > 1 else ''
                    val += '{}{} minute{}'.format(comma, us.tm_mins, plural)
                    comma = ', '
                if us.tm_secs:
                    plural = 's' if us.tm_secs > 1 else ''
                    val += '{}{} second{}'.format(comma, us.tm_secs, plural)
            elif key == 'network':
                ssid, passwd = item[1]
                passwd = '*' * len(passwd)
                val = "['{}'], ['{}']".format(ssid, passwd)
            else:
                val = item[1]
            log.print('{:9s} is {}'.format(key, val))

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
            self.time = time.monotonic_ns()
            self.diff = self.time - self.start_time
        self.start_time = None
        return self.time

class Display:
    def __init__(self):
        self.group = displayio.Group(max_size=4)
        self.font = bitmap_font.load_font("/IBMPlexMono-Medium-24_jep.bdf")
        self.font.load_glyphs('0123456789')
        self.hour_label = Label(self.font, max_glyphs=2)
        self.min_label = Label(self.font, max_glyphs=2)
        self.colon_label = Label(self.font, max_glyphs=1)
        self.setup_AM_PM()
        self.group.append(self.colon_label)
        self.group.append(self.hour_label)
        self.group.append(self.min_label)
        self.group.append(self.AM_PM_TileGrid)
        
        self.matrix = Matrix(bit_depth=5)   # bit_depth=5 allows 32 levels for each of R,G, and B
                                            # and this allows maximum dimming of the display
        
    def show(self):
        self.matrix.display.show(self.group)
        
    def setup_AM_PM(self):
        # Setup a palette for the AM/PM tilegrid
        self.bitmap_palette = displayio.Palette(2)
        self.bitmap_palette[0] = Colors.Black
        self.bitmap_palette[1] = Colors.Black
        
        # Create bitmap with 'AM' and 'PM'
        self.AM_PM_bitmap = displayio.Bitmap(10, 10, 2)
        for x in range(10):
            for y in range(10):
                self.AM_PM_bitmap[x, y] = 0
        A_pixels = ((0,1), (0,2), (0,3), (0,4), (1,0), (1,2), (2,0), (2,2), (3,1), (3,2), (3,3), (3,4))
        P_pixels = ((0,5), (0,6), (0,7), (0,8), (0,9), (1,5), (1,7), (2,5), (2,7), (3,5), (3,6), (3,7))
        M_pixels = ((5,0), (5,1), (5,2), (5,3), (5,4), (6,1), (7,2), (8,1), (9,0), (9,1), (9,2), (9,3), (9,4))
        for x,y in A_pixels:
            self.AM_PM_bitmap[x, y] = 1
        for x,y in P_pixels:
            self.AM_PM_bitmap[x, y] = 1
        for x,y in M_pixels:
            self.AM_PM_bitmap[x, y] = 1
            self.AM_PM_bitmap[x, y+5] = 1
            
        
        self.AM_PM_TileGrid = displayio.TileGrid(self.AM_PM_bitmap, pixel_shader=self.bitmap_palette,
                                            width=1, height=1, tile_width=10, tile_height=5)
        # Position the AM/PM on the display
        self.AM_PM_TileGrid.x = 48
        self.AM_PM_TileGrid.y = 26
        
        self.AM_PM_TileGrid[0] = 0
            
    # Update the time display
    def update(self):
        """ update the RGB Matrix display with the current time """
        now = Time2000.datetime(time_keeper.local_time_secs)
    
        hours = now[3]
        minutes = now[4]

        # Determine the display color
        color_option = options.get_actual_color()
        if hours >= options.get('night') or hours < options.get('day'):
            color_option = color_option[0]
        else:
            color_option = color_option[1]
            
        self.hour_label.color = color_option
        self.min_label.color = color_option
        self.colon_label.color = color_option

        # Handle AM/PM
        show_ampm = options.get('ampm')
        if not show_ampm:
            color_option = Colors.Black
        # 12 or 24 hour display
        if not options.get('24h'):
            self.bitmap_palette[1] = color_option
            if hours >= 12: # PM
                self.AM_PM_TileGrid[0] = 1
                hours -= 12
            else:           # AM
                self.AM_PM_TileGrid[0] = 0
            if hours == 0:
                hours = 12
        else:
            show_ampm = False
            self.bitmap_palette[1] = Colors.Black

        blink = options.get('blink')
        center = options.get('center')
        
        colon = ":"
        if blink:
            # blink the colon
            if time_keeper.clock.sqw.value:
                colon = " "
    
        self.hour_label.text = "{}".format(hours)
        self.min_label.text = "{:02d}".format(minutes)
        self.colon_label.text = colon
    
        if center and hours < 10:
            self.hour_label.x = 6
            self.min_label.x = 29
            self.colon_label.x = 21
        else:
            if hours < 10:
                self.hour_label.x = 13
            else:
                self.hour_label.x = 0
            self.min_label.x = 36
            self.colon_label.x = 28
    
        y_offset = -2 if show_ampm else 0
        self.hour_label.y = 16 + y_offset
        self.min_label.y = 16 + y_offset
        self.colon_label.y = 14 + y_offset
        
        self.show()

#  Start of main program

try:
    # setup the logger
    log = logger.log
           
    # Turn off the status neopixel
    #     The neopixel is WAY too bright for a clock in a dark room
    supervisor.set_rgb_status_brightness(0)
    
    i2c = busio.I2C(board.SCL, board.SDA)
    
    # setup the accelerameter
    lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
    _ = lis3dh.acceleration
    time.sleep(0.1)
    
    # set up the display
    display = Display()
    
    bool_vals = 'true, enable, enabled, yes, no, false, disable, disabled, no, off'
    hour_vals = '1 to 23'
    color_vals = 'red, green, auto'
    rotate_vals = '0, 180, auto'
    rtc_vals = "'mm/dd/yyyy hh:mm:ss', sync, nearest, +sec, -sec, +min, -min, +hour, -hour"
    history_vals = 'reset'
    
    
    # --- Options setup   option        validation                          value      function         saveable  display
    options = Options( {'24h' :      [(Command.testBool,Command.testNull),  False,    Options.replace,  True,     True,    bool_vals],
                        'blink' :    [(Command.testBool,Command.testNull),  True,     Options.replace,  True,     True,    bool_vals],
                        'center' :   [(Command.testBool,Command.testNull),  True,     Options.replace,  True,     True,    bool_vals],
                        'dim' :      [(Command.testBool,Command.testNull),  True,     Options.replace,  True,     True,    bool_vals],
                        'ampm':      [(Command.testBool,Command.testNull),  True,     Options.replace,  True,     True,    bool_vals],
                        'color' :    [(Command.testColor,Command.testNull), 'track',  Options.replace,  True,     True,    color_vals],
                        'night' :    [(Command.testHour,Command.testNull),  22,       Options.replace,  True,     True,    hour_vals],
                        'day' :      [(Command.testHour,Command.testNull),  6,        Options.replace,  True,     True,    hour_vals],
                        'logging' :  [(Command.testBool,Command.testNull),  True,     Options.replace,  True,     True,    bool_vals],
                        'rotation' : [(Command.testRotate,Command.testNull),'auto',   Options.replace,  True,     True,    rotate_vals],
                        'startup' :  [(Command.testNull,),                  None,     Options.show,     False,    True,    None],
                        'rtc' :      [(Command.testStr,),                   None,     Options.rtc,      False,    True,    rtc_vals],
                        'version' :  [(Command.testStr,),                   verstr,   Options.show,     False,    True,    None],
                        'memory' :   [(Command.testStr,),                   None,     Options.show,     False,    True,    None],
                        'time' :     [(Command.testStr,),                   None,     Options.show,     False,    True,    None],
                        'uptime' :   [(Command.testNull,),                  None,     Options.show,     False,    True,    None],
                        'save' :     [(Command.testStr,),                   None,     Options.save,     False,    False,   None],
                        'restore' :  [(Command.testStr,),                   None,     Options.restore,  False,    False,   None],
                        'restart' :  [(Command.testStr,),                   None,     Options.restart,  False,    False,   None],
                        'connect' :  [(Command.testStr,),                   None,     Options.connect,  False,    False,   None],
                        'host'    :  [(Command.testPair,Command.testNull), (None, None), Options.replace,  True,     True,    None],
                        'join'    :  [(Command.testStr,),                   None,     Options.join,     False,    False,   None],
                        'network' :  [(Command.testPair,Command.testNull), (None, None), Options.replace,  True,     True,    None],
                        'bye'     :  [(Command.testNull,),                  None,     Options.bye,      False,    False,   None],
                        'show' :     [(Command.testStr,),                   None,     Options.show,     False,    False,   None]} )
    
    logger.set_options(options)
    
    options.set_rotation(options.get('rotation'))
    options.restore('restore', Options.DEFAULT_FILE)
    
    command = Command(options)
    
    # Setup the buttons
    up_button = Button(board.BUTTON_UP)
    down_button = Button(board.BUTTON_DOWN)
    
    # Create the time_keeper 
    time_keeper = TimeKeeper()
    
    logger.set_time_keeper(time_keeper)
    
    log.message("MatrixClock Version   {}".format(verstr))
    
    # Setup the WiFi
    esp_mgr = wifi.ESP_manager('Clock')
    logger.set_esp_mgr(esp_mgr)
 
    major, minor, sub = sys.implementation.version
    log.message("Circuitpython {}.{}.{}".format(major, minor, sub))
    log.message("ESP32 firmware {}".format(esp_mgr.firmware_version))

     
    log.message("Clock started")
    
    # Create the console
    console = console.Console()
    
   
    # Loop forever, get commands, check buttons, and update the display
    keep_going = True
    inpbuffer = ''
    last_sqw = False
    timer = Timer()
    time_keeper.sync_time()
    while keep_going:
    
        try:
            # Every 50 ms: 
            
            # Check for and execute a command from the console
            timer.start
            cmdstr = console.get_line()
            if cmdstr:
                cmdstr = cmdstr.split()
                if len(cmdstr) == 1:
                    cmdstr.append('')
                command.run(cmdstr)
            
            # Check for and execute a command from socket
            cmdstr = esp_mgr.get_line()
            if cmdstr:
                cmdstr = cmdstr.split()
                if len(cmdstr) == 1:
                    cmdstr.append('')
                command.run(cmdstr)
             
            # Read the buttons
            pressed, pressed_time = up_button.read()
            # check if button just released
            if not pressed and pressed_time is not None:
                # button was pressed and released
                if pressed_time > 2.0:
                    log.print("Long press {} seconds".format(pressed_time))
                else:
                    # adjust clock to nearest minute
                    options.rtc(None, 'nearest')
                        
            pressed, pressed_time = down_button.read()
            # check if button just released
            if not pressed and pressed_time is not None:
                # button was pressed and released
                if pressed_time > 2.0:
                    log.print("Long press {} seconds".format(pressed_time))
                else:
                    # connect via socket to command terminal
                    # using default ssid/password and host/port from defaults.json
                    options.connect(None, None)
                        
            # Update the display time every 1/2 second
            # so that when using a blinking
            # cursor, it blinks once per second (1/2 second on,
            # 1/2 second off)
            
            # time_keeper.clock.sqw.value changes every 1/2 second
            sqw = time_keeper.clock.sqw.value
            if sqw != last_sqw:
                last_sqw = sqw
                display.update()
                
                # Once per second, increment the time
                if not sqw:
                    time_keeper.local_time_secs += 1
                    time_keeper.uptime += 1
    
            # If we processed some long running operation above,
            #   update the running time (local_time_secs) from the clock_chip
            timer.stop
            if timer.diff > 300_000_000:
                # update the time from the clock_chip
                time_keeper.sync_time()
            
        except Exception as e:
            log.message(e, add_time=False, traceback=True, exception_value=e)
                
            supervisor.reload()

        time.sleep(0.050)
        
except (KeyboardInterrupt, SystemExit):
    log.message("Exit to REPL")
    try:
        time_keeper.clock.chip.square_wave_frequency = 0
        time_keeper.clock.sqw.deinit()
    except NameError:
        pass

