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
The DS3231, DS1307 and PCF8523 clock modules are all supported
by MatrixClock.  MatrixClock uses the adafruit driver modules 
for these chips, although they were slightly modified to add 
support for the 1 Hz square wave outputs that these chips can 
generate. This 1 Hz square wave is the basis for the clock.

#### Results of tests by SwitchDoc Labs

| Device	  | Test Length (Seconds) |Measured PPM | Spec     |
|:---------|----------------------:|------------:|---------:|
| DS1307	  |   292,869             | 15 PPM      | 23 PPM   |
| DS3231	  | 3,432,851             | < 0.3 PPM   |  2 PPM   |
| PCF8523  | 3,432,851             | 24 PPM      | 29 PPM   |

The DS3231 is preferred because it is much more accurate than
the others.  
Adafruit sells breakout boards with each of these modules.

0.3 ppm is roughly one second in five weeks.  My experience with 
the DS3231 error has been about one second in ten weeks.

The RTC chip's 1Hz square wave output is connected to one of the 
input pins on the matrix portal.  The clock function uses that input
to keep track of the time and to update the display every 1/2 second.

The support modules (included in this repo) for the chips are:
* adafruit_ds3231
* adafruit_ds1307
* adafruit_pcf8523

MatrixClock will identify which clock chip you have and load
the appropriate module.  You only need to place the appropriate
module (or all of them) on the CIRCUITPY drive.  MatrixClock will
also detect to which pin (A0, A1, A2, A3, or A4) you have connected 
the clock chip's square wave output.

### Display
The Matrix Portal is designed specifically for the LED matrix
displays that Adafruit sells, and it works very well with 
them.  Any of the 64x32 displays can be used.

### Code
code.py, clock.py, console.py, and logger.py contain the logic
of the clock.

boot.py gets control on a hard reset and does two things:  

1. It disables auto-reload, which I find very annoying and which 
sometimes causes the CIRCUITPY drive to become read-only.
2. It reads the DOWN button on the Matrix Portal and, if the button 
is held down during the reset, it will make the CIRCUITPY drive  
writable via USB and read-only to the code.py program.  If the button
is not held down during the reset, then the CIRCUITPY drive will be
writable by the code.py program and read-only via USB.
The DOWN button must be held down at least until the time that the
'python' appears on the display.
If the CIRCUITPY drive is writeable to the program (button was not
held down during reset) then MatrixClock will log events to a file.

### IBMPlexMono Font
The font is from John Park's Network Connected RGB Matrix Clock project.
He had modified the IBMPlexMono font and I further modified it to my
taste.  This is a very nice font for this purpose.

## Installation

The following files from the repo must be copied to the root
directory of the Matrix Portal's CIRCUITPY drive:

* boot.py
* code.py
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

In addition to the files in this repo, the following are needed and
should be stored in the /lib directory of the CIRCUITPY drive.

*  adafruit_lis3dh
*  adafruit_register
*  adafruit_matrixportal
*  adafruit_io
*  adafruit_display_text
*  adafruit_bus_device
*  adafruit_bitmap_font
*  adafruit_esp32spi
  
### Operation
