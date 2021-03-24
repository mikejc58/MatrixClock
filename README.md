Matrix Clock project to run on Adafruit Matrix Portal with circuitpython

Requires:
  64x32 LED matrix        Adafruit 2276, 2277, 2278 or 2279
  DS3231 precision RTC    Adafruit 3013, 4282 or 255
  Adafruit Matrix Portal  Adafruit 4745
  
The code could easily be adapted to any platform that can
drive a 64x32 display

It uses a slightly modified version of the adafruit_ds3231 module.
(modified to allow use of the 1Hz square wave output of the ds3231)

The DS3231 1Hz square wave output is connected to an available 
input pin on the matrix portal.  The clock function uses that input
to keep track of the time and to update the display every 1/2 second.
You can specify to which pin on the Matrix Portal you have connected 
the square wave output, and whether you have an external pull-up
resistor on that pin (the squre wave output is an open drain transistor
and requires a pull-up; either an actual resistor pull-up to 3.3V or 
the software can provide an internal pull-up.

In addition to the files in this repo, the following are needed:

  adafruit_lis3dh
  neopixel
  adafruit_register
  adafruit_matrixportal
  adafruit_io
  adafruit_display_text
  adafruit_bus_device
  adafruit_bitmap_font
  
