import board
from digitalio import DigitalInOut
import busio
from adafruit_esp32spi import adafruit_esp32spi
import time

import logger

class ESP_manager:
    def __init__(self, nickname=''):
        self.spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        self.ready_pin = DigitalInOut(board.ESP_BUSY)
        self.cs_pin = DigitalInOut(board.ESP_CS)
        self.reset_pin = DigitalInOut(board.ESP_RESET)
        self.esp = adafruit_esp32spi.ESP_SPIcontrol( 
                self.spi, self.cs_pin, self.ready_pin, self.reset_pin)
                
        self.nickname = nickname
        self.ap = False
        self.esp.reset()

    @property
    def firmware_version(self):
        return str(self.esp.firmware_version, 'utf-8')
        
    def connect_status(self):
        txt = ''
        if self.ap:
            ssid = str(self.esp.ssid, 'utf-8')
            rssi = self.esp.rssi
            txt = '{}  {}  {} dBm'.format(ssid, self.esp.pretty_ip(self.esp.ip_address), rssi)
        return txt
    
    def connect_to_ap(self, ssid, password):
        self.disconnect_from_ap()
        if self.esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
            log.message('ESP32 found and in idle mode')
        
        log.message('Joining network via access point: {}'.format(str(ssid, 'utf8')))
        for cnt in range(2):
            try:
                self.esp.connect_AP(ssid, password, timeout_s=20)
            except RuntimeError as e:
                log.message("RuntimeError: {}".format(str(e)))
                continue
            if self.esp.is_connected:
                self.ap = True
                log.message('Joined with {}'.format(str(self.esp.ssid, 'utf-8')))
                log.message('Signal strength: {}'.format(self.esp.rssi))
                log.message('ESP32 IP address: {}'.format(self.esp.pretty_ip(self.esp.ip_address)))
                break
        else:
            log.message('Failed to join with {}'.format(ssid))
        
        return self.ap

    def disconnect_from_ap(self):            
        if self.ap:
            log.message("Disconnecting from AP")
            # self.esp.disconnect() leaves the ESP in a bad state, so don't do that just reset
            self.ap = None
        self.esp.reset()

log = logger.log
