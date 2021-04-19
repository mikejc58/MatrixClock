from adafruit_esp32spi import adafruit_esp32spi_socket

telnet_printable = 'abcdefghijklmnopqrstuvwxyz' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' + '0123456789' +  \
                   " (%&'()*+, -./!" + '"#$:;?| @[\]^_`{}~)' + '\n'
telnet_IAC = 255

telnet_cmds = {254: 'DONT', 253: 'DO  ', 252: 'WONT', 251: 'WILL', 250: 'SB  ',
               249: 'GA  ', 248: 'EL  ', 247: 'EC  ', 246: 'AYT ', 245: 'AO  ',
               244: 'IP  ', 243: 'BRK ', 242: 'DM  ', 241: 'NOP ', 240: 'SE  '
              }
telnet_cmd_codes = {'DONT': 254, 'DO': 253, 'WONT':252, 'WILL': 251,
                    'SB': 250, 'GA': 249, 'EL': 248, 'EC': 247, 'AYT': 246,
                    'AO': 245, 'IP': 244, 'BRK': 243, 'DM': 242, 'NOP': 241, 'SE': 240
                    }
               
telnet_opts = {1:   'Echo', 3: 'Suppress GA', 5: 'Status', 6: 'Timing Mark', 7: 'Remote Echo',
               18: 'Logout', 24: 'Terminal Type', 31: 'Negotiate Window Size', 32: 'Terminal Speed',
               33: 'Remote Flow Control', 34: 'Linemode', 35: 'X Display Location', 36: 'Environment Option',
               39: 'New Environment Option', 45: 'Suppress Local Echo'
              }

telnet_opt_codes = {'Echo': 1, 'Suppress GA': 3, 'Status': 5, 'Timing Mark': 6, 'Remote Echo': 7,
                    'Logout': 18, 'Terminal Type': 24, 'Negotiate Window Size': 31, 'Terminal Speed': 32,
                    'Remote Flow Control': 33, 'Linemode': 34, 'X Display Location': 35, 'Environment Option': 36,
                    'New Environment Option': 39, 'Suppress Local Echo': 45
                    }

class TelnetD:
    def __init__(self, esp_mgr):
        """ create the TelnetD object and start the server """
        self.esp_mgr = esp_mgr
        adafruit_esp32spi_socket.set_interface(self.esp_mgr.esp)
        self.inbuffer = ''
        self.cmds = []
        self.next_fn = self.state_text
        self.telnet_cmd = []
        self.client_socket = None
        self.server_socket = None
        self.termious = None        # termious hack
        self._start_server()

    def text_to_client(self, txt):
        """ send a line to the telnet client (add \r\n) """
        data = bytes(txt + '\r\n', 'utf-8')
        self.send_to_client(data)

    def send_to_client(self, data):
        """ send some bytes to the telnet client """
        if self.client_socket and self.client_socket.connected():
            try:
                self.client_socket.send(data)
            except RuntimeError:
                # socket is now closed
                pass
    
    def send_telnet_command(self, cmd):
        """ send a telnet command to the client """
        data = bytes(cmd)
        self.send_to_client(data)
    
    def termious_hack(self, byte):
        """ if the telnet client is 'termious' this hack is needed
            because termious doesn't properly support line mode (no Echo) """
        if byte == 10:
            # newline from termious
            data = bytes([13, 10])
            self.send_to_client(data)
        elif byte == 8:
            # CTRL-H (backspace from termious)
            if self.inbuffer:
                self.inbuffer = self.inbuffer[:-1]
            data = bytes([32, 8])
            self.send_to_client(data)
            
    # state machine functions
    # The state is set in self.next_fn to identify
    # which state function will process the next character        
    def state_text(self, byte):
        """ next byte is normal text or a telnet IAC """
        c = chr(byte)
        if byte == telnet_IAC:
            self.next_fn = self.state_cmd
            self.telnet_cmd = []
        elif c in telnet_printable:
            self.inbuffer += c
        if self.termious:
            self.termious_hack(byte)
    
    def state_cmd(self, byte):
        """ next byte is a telnet command """
        if byte in telnet_cmds:
            self.telnet_cmd.append(byte)
            if 251 <= byte <= 254:
                self.next_fn = self.state_option
            elif byte == 250:
                self.next_fn = self.state_sub
            else:
                self.handle_telnet_cmd(self.telnet_cmd)
                self.next_fn = self.state_text
        else:
            # unknown/invalid command
            self.next_fn = self.state_text
        
    def state_option(self, byte):
        """ next byte is an option """
        if byte in telnet_opts:
            self.telnet_cmd.append(byte)
            self.handle_telnet_cmd(self.telnet_cmd)
        self.next_fn = self.state_text
        
    def state_sub(self, byte):
        """ in a sub-option negotiation """
        # subnegotiation
        self.telnet_cmd.append(byte)
        if byte == telnet_IAC:
            self.next_fn = self.state_end_sub
        
    def state_end_sub(self, byte):
        """ next byte should be end of sub-option """
        self.telnet_cmd.append(byte)
        if byte == 240:
            self.handle_telnet_cmd(self.telnet_cmd)
            self.next_fn = self.state_text
        else:
            self.next_fn = self.state_sub
    
    
    def _add_to_buffer(self, data):
        """ add bytes read from client socket to the input buffer """
        for byte in data:
            self.next_fn(byte)        
        self._parse_cmds()
        
    def _parse_cmds(self):
        """ split out new commands and add them to the cmds list """
        lst = self.inbuffer.split('\n')
        # leave trailing text (not terminated by \n) in inbuffer
        self.inbuffer = lst.pop(-1)
        if lst:
            for cmd in lst:
                self.cmds.append(cmd)
                
    def get_cmd(self):
        """ return the next command, or None """
        return self.cmds.pop(0) if self.cmds else None
    
    def _close_client(self):
        """ close the client socket """
        if self.client_socket.socknum != adafruit_esp32spi_socket.NO_SOCKET_AVAIL:
            self.client_socket.close()
        self.client_socket = None
        
            
    def _start_server(self):
        """ start the telnet server listening on port 23 """
        self.server_socket = adafruit_esp32spi_socket.socket()
        self.esp_mgr.esp.start_server(23, self.server_socket.socknum)
        
    def check_client(self):
        """ if a client telnet is connected, check for input.
            if there is no client, check for new connections """
        ret_val = None
        if self.client_socket:
            # client exists
            ret_val = "Connected"
            if self.client_socket.connected():
                if self.client_socket.available():
                    data = self.client_socket.recv()
                    if data:
                        self._add_to_buffer(data)
                    else:
                        self._close_client()
            else:
                self._close_client()
                
        else:
            # check for new client
            ret_val = "Listening"
            # reset termious hack
            self.termious = None
            client_sock_num = self.esp_mgr.esp.socket_available(self.server_socket.socknum)
            if client_sock_num != adafruit_esp32spi_socket.NO_SOCKET_AVAIL:
                # new connection
                ret_val = "Connected"
                
                self.client_socket = adafruit_esp32spi_socket.socket(socknum=client_sock_num)
                
                self.send_telnet_command([telnet_IAC, telnet_cmd_codes['WONT'], telnet_opt_codes['Echo']])
                self.send_telnet_command([telnet_IAC, telnet_cmd_codes['WONT'], telnet_opt_codes['Suppress GA']])
        return ret_val
            
    def handle_telnet_cmd(self, telnet_cmd):
        """ process telnet command from the client telnet """
        print("Telnet cmd: {}".format(telnet_cmd))
        # termious hack
        if self.termious is None:
            if len(telnet_cmd) == 8:
                if telnet_cmd[0] == 250 and telnet_cmd[1] == 31:
                    self.termious = True
            if len(telnet_cmd) == 2:
                if telnet_cmd[0] == 251 and telnet_cmd[1] == 31:
                    self.termious = False

    

