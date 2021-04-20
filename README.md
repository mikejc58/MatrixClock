# Matrix Clock 
***
Circuitpython code to implement a clock using an Adafruit Matrix Portal
***
## Hardware Requirements:
|  Device                |   Source                          |
|:-----------------------|:----------------------------------|
| 64x32 LED matrix       | Adafruit 2276, 2277, 2278 or 2279 |
| Real Time Clock module | DS3231, DS1307 or PCF8523         |
| Adafruit Matrix Portal | Adafruit 4745                     |

### Real Time Clock module
The DS3231, DS1307 and PCF8523 clock modules are all supported by MatrixClock.  MatrixClock uses the adafruit driver modules for these chips, although they were slightly modified to add support for the 1 Hz square wave outputs that these chips can generate. This 1 Hz square wave is the basis for the clock.

Don't forget to install a CR1220 battery into the clock module!

#### Results of tests by SwitchDoc Labs

| Device	  | Test Length (Seconds) |Measured PPM | Spec     |
|:---------|----------------------:|------------:|---------:|
| DS1307	  |   292,869             | 15 PPM      | 23 PPM   |
| DS3231	  | 3,432,851             | < 0.3 PPM   |  2 PPM   |
| PCF8523  | 3,432,851             | 24 PPM      | 29 PPM   |

The DS3231 is preferred because it is much more accurate than the others.  Adafruit sells breakout boards with each of these modules.

0.3 ppm is roughly one second in five weeks.  My experience with the DS3231 error has been about one second in ten weeks.

The RTC chip's 1Hz square wave output is connected to one of the input pins on the matrix portal.  The clock function uses that input to keep track of the time and to update the display every 1/2 second.

The support modules (included in this repo) for the chips are:
* adafruit_ds3231
* adafruit_ds1307
* adafruit_pcf8523

Use the versions provided here, the modules in the adafruit bundle do not allow configuring the square wave output of the chips.

MatrixClock will identify which clock chip you have and load the appropriate module.  You only need to place the appropriate module (or all of them) on the CIRCUITPY drive.  MatrixClock will also detect to which pin (A0, A1, A2, A3, or A4) you have connected the clock chip's square wave output.

### Display
The Matrix Portal is designed specifically for the LED matrix displays that Adafruit sells, and it works very well with them.  Any of the 64x32 displays can be used.

## Features
1. The clock display is uncluttered, showing only the time.  There are number of options which control the appearance of the time.  These are:
 * color
 * 24h / 12h
 * am/pm
 * blinking colon (seconds)
 * time centered / fixed
 * automatic color change day / night
 * display rotation
2. The clock can be corrected (if the RTC chip's time drifts) by pressing a button to reset the time to the nearest minute.  With this, and a correct time source (atomic clock, NTP, etc), you can correct the time with a single button press when the minute changes.  This can also be done by a command to the clock over USB or Telnet.
3. The clock configuration can be modified via USB or Telnet over a network.

### Code
code.py, clock.py, console.py, wifi.py, telnet.py, datetime_2000.py, and logger.py contain the logic of the clock.

boot.py gets control on a hard reset and does two things:  

1. It disables auto-reload, which I find very annoying and which sometimes causes the CIRCUITPY drive to become read-only.
2. It reads the DOWN button on the Matrix Portal and, if the button is held down during the reset, it will make the CIRCUITPY drive writable via USB and read-only to the MatrixClock program.  If the button is not held down during the reset, then the CIRCUITPY drive will be writable by the MatrixClock program and read-only via USB. The DOWN button must be held down at least until the time that the 'python' appears on the display. If the CIRCUITPY drive is writeable to the program (button was not held down during reset) then MatrixClock can log events to a file and you can save configuration changes to the defaults.json file.

### IBMPlexMono Font
The font is from John Park's Network Connected RGB Matrix Clock project. He had modified the IBMPlexMono font and I further modified it to my taste.  This is a very nice font for this purpose.

## Installation

The following files from the repository must be copied to the root directory of the Matrix Portal's CIRCUITPY drive:

* boot.py (see below)
* code.py (see below)
* clock.py
* console.py
* logger.py
* wifi.py
* datetime_2000.py
* defaults.json
* IBMPlexMono-Medium-24_jep.bdf
* One (or all) of:
   adafruit_ds3231.py
   adafruit_ds1307.py
   adafruit_pcf8523.py

In addition to the files in this repository, the following are needed and should be stored in the /lib directory of the CIRCUITPY drive.

*  adafruit_lis3dh
*  adafruit_register
*  adafruit_matrixportal
*  adafruit_io
*  adafruit_display_text
*  adafruit_bus_device
*  adafruit_bitmap_font
*  adafruit_esp32spi

Before connecting the 64x32 matrix display, connect the Matrix Portal to your computer by USB.  (This way, your computer doesn't have to power the display).  
Now:

1. Install the latest ESP32 firmware onto the Matrix Portal.

    (See: https://learn.adafruit.com/upgrading-esp32-firmware)

2. Install the latest CircuitPython for the Matrix Portal.

3. Copy the Adafruit libraries listed above to the /lib directory on CIRCUITPY. 
 
4. Copy the files from this repository into the root directory, but copy code.py and boot.py last.  (This is because each time a file is copied to CIRCUITPY, CircuitPython will attempt to auto re-load code.py)

Note: As described above, boot.py will make the CIRCUITPY drive writable to the MatrixClock software, which makes it read-only to your USB connected computer.  If you need to make changes to CIRCUITPY (to add more files perhaps) you will need to press and hold the 'down' button on the Matrix Portal and press reset.  Hold the 'down' button at least until the re-boot is complete. This makes CIRCUITPY writable to your computer.

## Configuration

The clock needs to be configured when first set up.  You can configure most of the settings in the defaults.json file, but it is easiest to configure the clock using a USB serial console.  I've tested the following programs as the serial console for MatrixClock; all work well:
* PuTTY on Windows and Linux (select 'serial' at 115200 bps)
* screen on Linux and Mac (use 115200 bps)
* tio on Linux (use 115200 bps)
* Mu Editor on Linux and Mac

As mentioned above, you can do this step before connecting the 64x32 matrix display (so the computer doesn't have to provide power for it)

With the Matrix Portal connected to the computer via USB, bring up the serial console program you've selected and connect to the Matrix Portal.

Reset the Matrix Portal and you should get output like this:

```
                    - Options restored from defaults.json
                    - Clock chip identified as DS3231
                    - Square Wave detected on pin A2
 1/01/2000  0:00:29 - MatrixClock Version   3.1
 1/01/2000  0:00:29 - Circuitpython 6.1.0
 1/01/2000  0:00:29 - ESP32 firmware 1.7.1
 1/01/2000  0:00:29 - No network configured
 1/01/2000  0:00:29 - Clock started
No Network
```

If the RTC chip had not previously been set, it will now be set to Jan 1, 2000. Circuitpython 6.1.0 and ESP32 firmware 1.7.1 are the minimum levels required.

You can see the current clock configuration by typing the 'show' command.

```
show

color     is track
rotation  is auto
time      is 1/01/2000  7:12:07  Saturday
ampm      is True
center    is True
blink     is True
startup   is AUTO_RELOAD
night     is 22
day       is 6
24h       is False
memory    is 16320
autojoin  is True
dim       is True
connected is 
rtc       is 1/01/2000  7:12:07  Saturday   (DS3231)
telnet    is No Network
network   is ssid, ********
uptime    is 7 hours, 12 minutes
logging   is True
version   is 3.1  Circuitpython 6.2.0  ESP32 Nina 1.7.3
```

To set the time use the 'rtc' command:
```
rtc 4/20/2021 8:04:30

rtc       is 4/20/2021  8:04:31  Tuesday   (DS3231)
```
You can have the clock connect to your WiFi network by giving it your SSID and password using the 'network' command:
```
network myssid mypasswd

network   is myssid, **********
```
Replace myssid and mypasswd with your networks SSID and password.  Options changed need to be saved to the defaults.json file.  Do this by using the 'save' command. 
```
save

 4/20/2021  8:54:08 - Options saved to defaults.json
```
You can also save options to other files using 'save filename'.  To restore a saved options file, use 'restore filename'

To connect to the WiFi network you can use the 'join' command.  Either 'join' with no parameters to join the network configured with the 'network' option, or 'join ssid,passwd' to join another network.

The 'autojoin' option controls whether MatrixClock will attempt to join the configured network automatically when it is restarted (by 'restart' command, by reset button or by power-on)
```
autojoin on

autojoin  is True
```
Before continuing, make sure that MatrixClock successfully connects to your network by using the 'restart' command.  You should see:
```
restart
 4/20/2021  9:10:07 - Restarting MatrixClock

Code stopped by auto-reload.
soft reboot

Auto-reload is off.

code.py output:
                    - Options restored from defaults.json
                    - Clock chip identified as DS3231
                    - Square Wave detected on pin A2
 4/20/2021  9:10:15 - MatrixClock Version   3.1
 4/20/2021  9:10:15 - Circuitpython 6.2.0
 4/20/2021  9:10:15 - ESP32 firmware 1.7.3
 4/20/2021  9:10:15 - ESP32 found and in idle mode
 4/20/2021  9:10:15 - Joining network via access point: myssid
 4/20/2021  9:10:15 - Joined with myssid
 4/20/2021  9:10:15 - Signal strength: -44
 4/20/2021  9:10:15 - ESP32 IP address: 192.168.1.96
 4/20/2021  9:10:15 - Joined with myssid
 4/20/2021  9:10:15 - Clock started
Listening  port 23
```
'Listening  port 23' means that MatrixClock is listening for a Telnet client to connect on port 23.

Once the clock is configured to autojoin your WiFi network, you won't need to have it connected by USB to your computer anymore.  You can disconnect the USB, and attach the Matrix Portal to the 64x32 matrix display.  Power the Matrix Portal with a USB power supply sufficient to power the display too.  A 2 amp power supply should be more than enough.

### Operation

Once configured, the MatrixClock needs only power to its USB port to operate.  Twice a year, you may need to update the time for daylight savings time.  This can be done by connecting to the clock using a Telnet client on your computer.  I have tested PuTTY on Windows and Linux, telnet on Linux and Termius on a Mac and on an iPhone.  All work well.  On Termius you must select 'Backspace as CTRL+H'  The sockets implementation in Circuitpython in the Matrix Portal is too slow to use character mode, so linemode telnet is used instead.  This means that the ability to edit commands before you press enter is a function of the telnet client you use.

Once connected through telnet (or if you prefer through USB to your computer) you can enter the 'rtc' command to set the hour forward (in the spring) and to set the hour back (in the fall).
```
rtc
rtc       is 4/20/2021 10:10:07  Tuesday   (DS3231)
rtc +hour
rtc       is 4/20/2021 11:10:15  Tuesday   (DS3231)
rtc -hour
rtc       is 4/20/2021 10:10:20  Tuesday   (DS3231)
```
Of course, any other changes to the configuration can be accomplished in this way too.
Some examples:
```
ampm off
ampm      is False
24h on
24h       is True
24h disable
24h       is False
```
To discover what values are valid for an option, enter the option followed by a '?'.  Examples:
```
color ?
color valid parameters: red, green, auto
rtc ?
rtc valid parameters: 'mm/dd/yyyy hh:mm:ss', sync, nearest, +sec, -sec, +min, -min, +hour, -hour
blink ?
blink valid parameters: true, enable, enabled, yes, on, false, disable, disabled, no, off
```
Only one telnet connection is allowed at a time, if you disconnect your telnet client, you can then reconnect from elsewhere.


