import board
from digitalio import DigitalInOut
import busio
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_socket
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
        self.socket = None
        self.inbuffer = ''
        self.cmds = []
        self.esp.reset()

    @property
    def firmware_version(self):
        return str(self.esp.firmware_version, 'utf-8')

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

    def connect_to_socket(self, host, port):
        self.disconnect_from_socket()
        adafruit_esp32spi_socket.set_interface(self.esp)
        my_sock = adafruit_esp32spi_socket.socket()
        try:
            ip = self.esp.get_host_by_name(host)
        except RuntimeError as e:
            if str(e) == 'Failed to request hostname':
                log.print("Host {} not found".format(host))
            ip = None
        if ip:        
            for _ in range(8):
                try:
                    my_sock.connect((ip, port))
                    if my_sock.connected():
                        self.socket = my_sock
                        if self.nickname:
                            self.send_to_socket('nickname ' + self.nickname)
                        break
                except RuntimeError as e:
                    if str(e) == 'Expected 01 but got 00':
                        log.message("Connection to {}, port {} failed; trying port {}".format(host, port, port+1))
                        port += 1
                    elif str(e) == 'ESP32 not responding':
                        log.message("Runtime Error '{}'".format(str(e)))
                        break
        if self.socket:
            return port
        return None
        
    def disconnect_from_socket(self, send_bye=True):
        if self.socket:
            log.message("Disconnecting from socket")
            if send_bye:
                self.send_to_socket('bye')
            time.sleep(1)
            self.socket.close()
            self.inbuffer = ''
            self.cmds = []
            self.socket = None
            
    def disconnect_from_ap(self):            
        if self.ap:
            log.message("Disconnecting from AP")
            self.disconnect_from_socket()
            self.ap = None
        self.esp.reset()
    
    def send_to_socket(self, txt):
        if self.socket_connected:
            data = bytes(txt + '\n', 'utf-8')
            self.socket.send(data)
    
    def recv_from_socket(self):
        if self.socket_connected and self.socket.available():
            data = self.socket.recv()
            if data:
                txt = str(data, 'utf-8')
                self.inbuffer += txt
                lst = self.inbuffer.split('\n')
                self.inbuffer = lst.pop(-1)
                if lst:
                    for cmd in lst:
                        self.cmds.append(cmd)
            else:
                # connection has been closed
                self.disconnect_from_socket()
    
    @property
    def socket_connected(self):
        return self.socket and self.socket.connected()
    
    def get_line(self):
        self.recv_from_socket()
        cmd = None
        if self.cmds:
            cmd = self.cmds.pop(0)
        return cmd
    
log = logger.log
