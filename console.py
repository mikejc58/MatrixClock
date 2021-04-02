# Console input over CircuitPython USB serial

# supports editing lines with backspace, delete and left and right arrows
# supports command history with up and down arrows

# call get_line() each time around your main loop.  It accumulates 
# characters with each call.  Until it gets an 'enter' it returns None.  
# When the line is completed with the 'enter' key it then returns
# the line as a string

import supervisor
import sys

class Console:
    # normalchars = '0123456789/: abcdefghijklmnopqrstuvwxyz'
    escape_tree = {'[': {'A':           'uparrow',      # 0x1b5d41
                         'B':           'downarrow',    # 0x1b5d42
                         'C':           'rightarrow',   # 0x1b5d43
                         'D':           'leftarrow',    # 0x1b5d44
                         '2': {'\x7e' : 'insert'},      # 0x1b5d327e
                         '3': {'\x7e' : 'delete'}       # 0x1b5d337e
                         }
                   }
    seq = {'uparrow':    '\x1b[A', 
           'downarrow':  '\x1b[B', 
           'rightarrow': '\x1b[C', 
           'leftarrow':  '\x1b[D',
           'insert':     '\x1b[2\x7e', 
           'delete':     '\x1b[3\x7e'}
           
    max_history = 20
    
    def __init__(self):
        self._reset_inbuffer()
        self.reset_history()
        self.escape = None
    
    def get_history(self):
        """return the history list"""
        return self.history
        
    def reset_history(self):
        """clear the history list"""
        self.history = ['']
        self.history_pos = 1
    
    def _reset_inbuffer(self):
        """reset the accumulated input buffer to null"""
        self.inbuffer = ''
        self.cursor = 0
    
    @staticmethod
    def _show(buf, cursor):
        """show the buffer and position the cursor"""
        print("\r{} \r{}".format(buf, Console.seq['rightarrow']*cursor), end='')

    @staticmethod
    def _erase_and_show(oldlen, buf, cursor):
        """erase the line (for oldlen) and show the buffer and position the cursor"""
        print("\r{}\r".format(' '*oldlen), end='')
        Console._show(buf, cursor)
    
    def _delete_and_show(self):
        """delete a character at the cursor position and show the result"""
        self.inbuffer = self.inbuffer[:self.cursor] + self.inbuffer[self.cursor+1:]
        Console._show(self.inbuffer, self.cursor)
        
    def _insert_and_show(self, ch):
        """insert a character at the cursor position and show the result"""
        self.inbuffer = self.inbuffer[:self.cursor] + ch + self.inbuffer[self.cursor:]
        self.cursor += 1
        Console._show(self.inbuffer, self.cursor)

    def _add_to_history(self, buf):
        """add a line to the history buffer"""
        if buf != self.history[0]:
            self.history.insert(0, buf)
            if len(self.history) > Console.max_history:
                self.history.pop()
    
    def _continue_escape(self, ch):
        """continue processing an escape sequence"""
        try:
            nxt = self.escape[ch[0]]
            if isinstance(nxt, str):
                # escape sequence is complete
                self.escape = None
                if nxt == 'uparrow':
                    if len(self.history) > self.history_pos:
                        oldlen = len(self.inbuffer)
                        self.inbuffer = self.history[self.history_pos-1]
                        self.cursor = len(self.inbuffer)
                        self.history_pos += 1
                        Console._erase_and_show(oldlen, self.inbuffer, self.cursor)
                        
                elif nxt == 'downarrow':
                    oldlen = len(self.inbuffer)
                    if self.history_pos > 1:
                        self.history_pos -= 1
                        if self.history_pos > 1:
                            self.inbuffer = self.history[self.history_pos-2]
                            self.cursor = len(self.inbuffer)
                        else:
                            self._reset_inbuffer()
                    else:
                        self._reset_inbuffer()
                    Console._erase_and_show(oldlen, self.inbuffer, self.cursor)
                    
                elif nxt == 'leftarrow':
                    if self.cursor > 0:
                        print(Console.seq['leftarrow'], end='')
                    # if self.cursor > 0:
                        self.cursor -= 1
                        
                elif nxt == 'rightarrow':
                    if self.cursor < len(self.inbuffer):
                        print(Console.seq['rightarrow'], end='')
                        self.cursor += 1
                        
                elif nxt == 'delete':
                    if self.cursor < len(self.inbuffer):
                        self._delete_and_show()                        
                        
            else:
                # go to next level in escape sequence
                self.escape = nxt
                
        except KeyError:
            # invalid escape sequence - ignore it
            self.escape = None
            
    
    def get_line(self):
        """accumulate characters in buffer.  return None on each call
           until 'enter' is pressed, then return the complete command"""
        line_str = None
        while supervisor.runtime.serial_bytes_available:
            ch = sys.stdin.read(1)
            
            if self.escape:
                # continue the escape sequence
                self._continue_escape(ch)
            
            # handle escape
            elif ch[0] == '\x1b':
                # start the escape sequence
                self.escape = Console.escape_tree
                
            # handle backspace
            elif ch[0] == '\x7f':
                if self.cursor > 0:
                    self.cursor -= 1
                    self._delete_and_show()
                    
            # handle newline
            elif ch[0] == '\n':
                print('')
                if self.inbuffer:
                    self._add_to_history(self.inbuffer)
                    line_str = self.inbuffer
                self._reset_inbuffer()
                self.history_pos = 1
                break
                
            # handle normal characters
            else:
                self._insert_and_show(ch)
                
        return line_str        
