import supervisor
import storage
import digitalio
import board
import time

supervisor.disable_autoreload()
print("*** Disabling auto-reload.")

button = digitalio.DigitalInOut(board.BUTTON_DOWN)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

time.sleep(0.25)

if button.value == True:   # button not pressed
    print("DOWN button not pressed")
    print("Making filesystem writable by code.py")
    print("Not writable via USB!")
    storage.remount("/", False)
else:
    print("DOWN button pressed")
    print("Making filesystem writable by USB")
    print("Not writable by code.py")
    
