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

VERSION={"MAJOR": 3, "MINOR": 105}
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
import neopixel
import sys
import supervisor
from adafruit_register import i2c_bit
from adafruit_bus_device.i2c_device import I2CDevice
import adafruit_lis3dh
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix

import console
import clock
import logger            
            
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
    def __init__(self):
        self.blink_colon = True

        self.clock = clock.Clock(i2c)
        self.local_time_secs = time.mktime(self.clock.datetime_at_second_boundary)
        

    def update_chip(self, val):
        new_time = self.clock.update_chip(val)
        if new_time is None:
            return "Invalid date/time"
        self.local_time_secs = new_time
        return None

    # Format clock_chip data
    def format_chip(self):
        dstime = time.mktime(self.clock.chip.datetime)
        return "{} {}".format(self.get_formatted_date(dstime), self.get_formatted_time(dstime))

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
                alternate = time_keeper.update_chip(val)
                
        if show:
            self.show('show', 'rtc', alt_text=alternate)

    def history(self, key, val, show=True):
        val = val.strip()
        if val:
            if val == 'reset':
                console.reset_history()
        if show:
            self.show('show', 'history')
                
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
            elif key == 'rtc':
                val = time_keeper.format_chip().strip()
            elif key == 'memory':
                val = gc.mem_free()
            elif key == 'time':
                val = '{} {}'.format(time_keeper.get_formatted_date(), time_keeper.get_formatted_time()).strip()
            elif key == 'history':
                val = console.get_history()
            else:
                val = item[1]
            print('{:9s} is {}'.format(key, val))

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
try:
    # setup the logger
    log = logger.log
    log.message("MatrixClock Version   {}".format(verstr))
            
    # Turn off the status neopixel
    #     The neopixel is WAY too bright for a clock in a dark room
    neoled = neopixel.NeoPixel(board.NEOPIXEL, 1)
    neoled.brightness = 0.05
    neoled.fill((0, 0, 0))
    
    i2c = busio.I2C(board.SCL, board.SDA)
    
    # setup the accelerameter for later use
    lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
    _ = lis3dh.acceleration
    time.sleep(0.1)
    
    # set up the display
    display = Display()
    
    # --- Options setup   option        validation                         value      function         saveable  display
    options = Options( {'24h' :      [(Command.testBool,),                 False,    Options.replace,  True,     True],
                        'blink' :    [(Command.testBool,),                 True,     Options.replace,  True,     True],
                        'center' :   [(Command.testBool,),                 True,     Options.replace,  True,     True],
                        'dim' :      [(Command.testBool,),                 True,     Options.replace,  True,     True],
                        'ampm':      [(Command.testBool,),                 True,     Options.replace,  True,     True],
                        'color' :    [(Command.testColor,),                'track',  Options.replace,  True,     True],
                        'night' :    [(Command.testHour,),                 22,       Options.replace,  True,     True],
                        'day' :      [(Command.testHour,),                 6,        Options.replace,  True,     True],
                        'logging' :  [(Command.testBool,),                 True,     Options.replace,  True,     True],
                        'rotation' : [(Command.testRotate,),               'auto',   Options.replace,  True,     True],
                        'rtc' :      [(Command.testStr,),                  None,     Options.rtc,      False,    True],
                        'version' :  [(Command.testStr,),                  verstr,   Options.show,     False,    True],
                        'memory' :   [(Command.testStr,),                  None,     Options.show,     False,    True],
                        'time' :     [(Command.testStr,),                  None,     Options.show,     False,    True],
                        'save' :     [(Command.testStr,),                  None,     Options.save,     False,    False],
                        'restore' :  [(Command.testStr,),                  None,     Options.restore,  False,    False],
                        'history' :  [(Command.testStr,),                  None,     Options.history,  False,    True],
                        'restart' :  [(Command.testStr,),                  None,     Options.restart,  False,    False],
                        'show' :     [(Command.testStr,),                  None,     Options.show,     False,    False]} )
    
    logger.set_options(options)
    
    options.set_rotation(options.get('rotation'))
    options.restore('restore', Options.DEFAULT_FILE)
    
    command = Command(options)
    
    # Setup the buttons
    up_button = Button(board.BUTTON_UP)
    down_button = Button(board.BUTTON_DOWN)
    
    # Clock_chip = Clock(i2c).identify()
    
    # Create the time_keeper 
    time_keeper = TimeKeeper()
    
    logger.set_time_keeper(time_keeper)
    
    log.message("Clock started")
    time_keeper.local_time_secs = time.mktime(time_keeper.clock.chip.datetime)
    
    # Create the console
    console = console.Console()
    
    # Loop forever, get commands, check buttons, and update the display
    keep_going = True
    inpbuffer = ''
    last_sqw = False
    timer = Timer()

    while keep_going:
    
        try:
            # just force a read of the clock chip to see if something bad happens
            # timex = time_keeper.clock.chip.datetime
            # Check for and execute a command from the console
            timer.start
            cmdstr = console.get_command()
            if cmdstr:
                command.run(cmdstr)
            # Every 50 ms: 
            # Read the buttons
             
            pressed, pressed_time = up_button.read()
            # check if button just released
            if not pressed and pressed_time is not None:
                # button was pressed and released
                if pressed_time > 2.0:
                    print("Long press {} seconds".format(pressed_time))
                else:
                    # adjust clock to nearest minute
                    options.clock_chip(None, 'nearest')
                        
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
                if sqw:
                    time_keeper.local_time_secs += 1
    
            # If we processed some long running operation above,
            #   update the running time (local_time_secs) from the clock_chip
            timer.stop
            if timer.diff > 300_000_000:
                # update the time from the clock_chip
                time_keeper.local_time_secs = time.mktime(time_keeper.clock.datetime_at_second_boundary)
            
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

