# Console input over CircuitPython USB serial

import supervisor
import sys

class Console:
    normalchars = '0123456789/: abcdefghijklmnopqrstuvwxyz'
    escape_tree = {'[': {'A': 'uparrow',
                         'B': 'downarrow',
                         'C': 'rightarrow',
                         'D': 'leftarrow',
                         '2': {'\x7e' : 'insert'},
                         '3': {'\x7e' : 'delete'}
                         }
                   }
    def __init__(self):
        self.inbuffer = ''
        self.escape = None
        self.escape_decode = None
        self.history = ['']
        self.history_pos = 1
    
    def get_history(self):
        return self.history
        
    def reset_history(self):
        self.history = ['']
        self.history_pos = 1
    
    def get_command(self):
        cmdstr = None
        while supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            if self.escape:
                # in an escape sequence
                try:
                    nxt = self.escape[ch[0]]
                    if isinstance(nxt, str):
                        # sequence is complete
                        escape_decode = nxt
                        self.escape = None
                        if nxt == 'uparrow':
                            if len(self.history) > self.history_pos:
                                print("\r{}\r".format(' '*len(self.inbuffer)), end='')
                                
                                self.inbuffer = self.history[self.history_pos-1]
                                print(self.inbuffer, end='')
                                self.history_pos += 1
                        if nxt == 'downarrow':
                            if self.history_pos > 1:
                                self.history_pos -= 1
                                print("\r{}\r".format(' '*len(self.inbuffer)), end='')
                                if self.history_pos > 1:
                                    self.inbuffer = self.history[self.history_pos-2]
                                else:
                                    self.inbuffer = ''
                            else:
                                self.inbuffer = ''
                            print(self.inbuffer, end='')
                                
                                
                    else:
                        # go to next level in sequence
                        self.escape = nxt
                except KeyError:
                    # invalid escape sequence - ignore it
                    self.escape = None
            
            # handle escape
            elif ch[0] == '\x1b':
                self.escape = Console.escape_tree
                # now in an escape sequence
                
            # handle backspace
            elif ch[0] == '\x7f':
                if len(self.inbuffer) > 0:
                    self.inbuffer = self.inbuffer[:-1]
                    # return to start of line, print the shortened string, 
                    # print a blank over the deleted character,
                    # use escape sequence to move the cursor left one space
                    print("\r{} \x1b\x5b\x44".format(self.inbuffer), end='')
                    
            # handle newline
            elif ch[0] == '\n':
                print('')
                if self.inbuffer != '':
                    if self.inbuffer != self.history[0]:
                        self.history.insert(0, self.inbuffer)
                        if len(self.history) > 20:
                            self.history.pop()
                    cmdstr = self.inbuffer.split()
                    if len(cmdstr) == 1:
                        cmdstr.append('')
                self.inbuffer = ''
                self.history_pos = 1
                
            # handle normal characters
            else:
                self.inbuffer += ch
                print("{}".format(ch), end='')
        return cmdstr        
