# Matrix Clock

# Runs on an Adafruit Matrix Portal with 64x32 RGB Matrix display
# Requires a DS3231 Precision Real Time Clock

# Square wave input pins available on Matrix Portal (A1, A2, A3, A4)
#  set Pin to match how your Matrix Portal is wired to the DS3231 SQW pin
#  set Pull_Up_Required to False if you have an external pull-up resistor
#      attached to the Pin
Square_Wave_Pin = 'A3'
Square_Wave_Pull_Up_Required = True

VERSION={"MAJOR": 3, "MINOR": 2}
verstr = '{}.{}'.format(VERSION['MAJOR'], VERSION['MINOR'])

import gc
import time
import board
import busio
import digitalio
import json
import displayio
import neopixel
import sys
import supervisor
import adafruit_lis3dh
import adafruit_ds3231
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix

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
        
class Logger:
    def __init__(self):
        self.AVAILABLE = True
        
    # Log messages to message_log.txt on the CIRCUITPY filesystem
    def message(self, text, do_print=True, add_time=True, traceback=False, exception_value=None):
        outtext = "                    - {}".format(text)
        try:
            if add_time:
                outtext = "{} {} - {}".format(time_keeper.get_formatted_date(), time_keeper.get_formatted_time(), text)
        except NameError:
            pass
        if do_print:
            print(outtext)
            if traceback:
                sys.print_exception(exception_value)
        if self.AVAILABLE and options.get('logging'):
            try:
                try:
                    with open("/message_log.txt", "a") as wf:
                        wf.write(outtext + "\n")
                        if traceback:
                            sys.print_exception(exception_value, wf)
                        wf.flush()
                except OSError as e:
                    err_code = e.args[0]
                    self.AVAILABLE = False
                    options.replace('logging', False)
                    if err_code == 28:
                        self.message("Filesystem is full - logging disabled")
                    elif err_code == 30:
                        self.message("Filesystem is read-only - logging disabled")
                    else:
                        self.message("Logging got OSError ({}) - logging disabled".format(err_code))
            except:
                self.AVAILABLE = False
                options.replace('logging', False)
                self.message("Unexpected exception while logging - logging disabled")

# Class to keep track of the time
class TimeKeeper:     
    def __init__(self):
        self.blink_colon = True
        self.ds3231 = None
        self.was_dst = None
        self.dst_offset = 0
        # self.url = TimeKeeper.BASEURL
        self.last_timezone = None
        self.timezone = None
        self.timezone_change = False
        
        self.local_time_secs = 0

        self._initialize_ds3231()
        self.setup_sqw(Square_Wave_Pin, Square_Wave_Pull_Up_Required)
        self._initialize_time()
        
        log.message("Version   {}".format(verstr))


    # Initialize ds3231
    def _initialize_ds3231(self):
        # Check for ds3231 RTC
        detected = False
        while not i2c.try_lock():
            pass
        for x in i2c.scan():
            if x == 0x68:
                detected = True
                break
        i2c.unlock()
        if detected:
            self.ds3231 = adafruit_ds3231.DS3231(i2c)
            self.ds3231.set_1Hz_SQW()
            self.local_time_secs = time.mktime(self.ds3231.datetime)
        else:
            log.message("ds3231 RTC not found")
            exit()

    def setup_sqw(self, pin, pullup):
        try:
            SQW_PIN = eval('board.' + pin)
            log.message("Square Wave Pin == {}".format(SQW_PIN))
        except AttributeError:
            log.message("Invalid Square Wave Pin specified - {}".format(pin))
            while True:
                pass
        self.sqw = digitalio.DigitalInOut(SQW_PIN)
        self.sqw.direction = digitalio.Direction.INPUT
        if pullup:
            self.sqw.pull = digitalio.Pull.UP
            
        
    # Format ds3231 data
    def format_ds3231(self):
        dstime = time.mktime(self.ds3231.datetime)
        return "{} {}  (power lost={}) ".format(self.get_formatted_date(dstime), self.get_formatted_time(dstime), self.ds3231.power_lost)

    # update the time/date stored in the ds3231
    def update_ds3231(self, val):
        try:
            if isinstance(val, int):
                secs = time.mktime(self.ds3231.datetime_at_second_boundary)
                self.ds3231.datetime = time.localtime(secs+val)
            elif val == 'nearest':
                dt = self.ds3231.datetime
                secs = time.mktime(dt)
                sec = dt[5]
                secs -= sec
                if sec > 30:
                    secs += 60
                self.ds3231.datetime = time.localtime(secs)
            else:
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
            self.local_time_secs = time.mktime(self.ds3231.datetime)
        except:
            return "Invalid date/time"

    def _initialize_time(self):
        self.local_time_secs = time.mktime(self.ds3231.datetime)

    def get_formatted_time(self, timeis=None):
        if not timeis:
            timeis = self.local_time_secs
        ts = time.localtime(timeis)
        fmt = "{:2d}:{:02d}:{:02d}".format(ts.tm_hour, ts.tm_min, ts.tm_sec)
        return fmt

    def get_formatted_date(self, timeis=None):
        if not timeis:
            timeis = self.local_time_secs
        ts = time.localtime(timeis)
        fmt = "{:2d}/{:02d}/{}".format(ts.tm_mon, ts.tm_mday, ts.tm_year)
        return fmt
        
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
        if key != 'logging' or val is False or log.AVAILABLE:
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
        display.matrix.display.rotation = val

    def ds3231(self, key, val, show=True):
        alternate = None
        val = val.strip()
        if val:
            # val can be 'nearest', '+xxx', '-xxx' (where xxx is sec[ond], min[ute], h[ou]r) or 'mm/dd/yyyy hh:mm:ss'
            
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
                alternate = time_keeper.update_ds3231(val)
                
        if show:
            self.show('show', 'ds3231', alt_text=alternate)
                
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
            log.message(txt)
            
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
            txt = str(e).split(']')
            if len(txt) > 1:
                txt = txt[1]
            else:
                txt = txt[0]
            log.message(txt)

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
    
        now = time.localtime(time_keeper.local_time_secs)
    
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
            if time_keeper.sqw.value:
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

# setup the logger
log = Logger()
        
# Turn off the status neopixel
#     The neopixel is WAY too bright for a clock in a dark room
neoled = neopixel.NeoPixel(board.NEOPIXEL, 1)
neoled.brightness = 0.05
neoled.fill((0, 0, 0))

# setup the accelerameter for later use
i2c = busio.I2C(board.SCL, board.SDA)
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
_ = lis3dh.acceleration
time.sleep(0.1)

# set up the display
display = Display()
        
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
                    'ds3231' :   [(Command.testStr,),                  None,     Options.ds3231,   False,    True],
                    'version' :  [(Command.testStr,),                  verstr,   Options.show,     False,    True],
                    'memory' :   [(Command.testStr,),                  None,     Options.show,     False,    True],
                    'time' :     [(Command.testStr,),                  None,     Options.show,     False,    True],
                    'save' :     [(Command.testStr,),                  None,     Options.save,     False,    False],
                    'restore' :  [(Command.testStr,),                  None,     Options.restore,  False,    False],
                    'show' :     [(Command.testStr,),                  None,     Options.show,     False,    False]} )

options.set_rotation(options.get('rotation'))
options.restore('restore', Options.DEFAULT_FILE)

command = Command(options)

# Setup the buttons
up_button = Button(board.BUTTON_UP)
down_button = Button(board.BUTTON_DOWN)

# Create the time_keeper 
time_keeper = TimeKeeper()

# Test that square wave is actually working
time.sleep(2)
end_time = time.monotonic_ns() + 2 * (10**9)
sqw_val = time_keeper.sqw.value
while time.monotonic_ns() < end_time:
    if time_keeper.sqw.value != sqw_val:
        break
if time.monotonic_ns() >= end_time:
    log.message("No squarewave detected on pin {}".format(Square_Wave_Pin))
    sys.exit()

time_keeper.local_time_secs = time.mktime(time_keeper.ds3231.datetime)
log.message("Clock started")

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
                options.ds3231(None, 'nearest')
                    
        # Every 1/2 second:
        # Update the display time every 1/2 second
        # so that when using a blinking
        # cursor, it blinks once per second (1/2 second on,
        # 1/2 second off)
        
        # time_keeper.sqw.value changes every 1/2 second
        sqw = time_keeper.sqw.value
        if sqw != last_sqw:
            last_sqw = sqw
            display.update()
            
            # Once per second, increment the time
            if sqw:
                time_keeper.local_time_secs += 1

        # If we processed some long running operation above,
        #   update the running time (local_time_secs) from the ds3231
        timer.stop
        if timer.time > 300_000_000:
            # update the time from the ds3231
            time_keeper.local_time_secs = time.mktime(time_keeper.ds3231.datetime)
            log.message("long wait - local_time updated from ds3231")
                    
    except Exception as e:
        log.message(e, add_time=False, traceback=True, exception_value=e)
            
        supervisor.reload()

    
    time.sleep(0.050)

