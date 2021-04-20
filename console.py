# Console input over CircuitPython USB serial

# supports editing lines with backspace, delete and left and right arrows
# supports command history with up and down arrows

# call get_line() each time around your main loop.  It accumulates 
# characters with each call.  Until it gets an 'enter' it returns None.  
# When the line is completed with the 'enter' key it then returns
# the line as a string

# Console has been tested with tio (simple terminal editor) and
# with the Mu Editor and works well with them.  It may work with
# others as well.

import supervisor
import sys

class Console:
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
        self.edited = False
        
    def _fill_inbuffer(self, cmd):
        """fill the input buffer with a command"""
        self.inbuffer = cmd
        self.cursor = len(cmd)
        self.edited = False
    
    @staticmethod
    def _show(buf, new_cursor, current_cursor):
        """show the buffer and position the cursor"""
        print("{}{}{}".format(Console.seq['leftarrow']*(current_cursor), buf, 
                              Console.seq['leftarrow']*(len(buf)-new_cursor)), end='')

    @staticmethod
    def _erase_and_show(oldlen, buf, cursor):
        """erase the line (for oldlen) and show the buffer and position the cursor"""
        print("{}{}".format(Console.seq['leftarrow']*oldlen, ' '*oldlen), end='')
        Console._show(buf, cursor, oldlen)
    
    def _delete_and_show(self, current_cursor):
        """delete a character at the cursor position and show the result"""
        self.edited = True
        self.inbuffer = self.inbuffer[:self.cursor] + self.inbuffer[self.cursor+1:]
        Console._show(self.inbuffer+' ', self.cursor, current_cursor)
        
    def _insert_and_show(self, ch):
        """insert a character at the cursor position and show the result"""
        self.edited = True
        self.inbuffer = self.inbuffer[:self.cursor] + ch + self.inbuffer[self.cursor:]
        currrent_cursor = self.cursor
        self.cursor += 1
        Console._show(self.inbuffer, self.cursor, currrent_cursor)

    def _add_to_history(self, buf):
        """add a line to the history buffer"""
        if self.edited and buf != self.history[0]:
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
                        self._fill_inbuffer(self.history[self.history_pos-1])
                        self.history_pos += 1
                        Console._erase_and_show(oldlen, self.inbuffer, self.cursor)
                        
                elif nxt == 'downarrow':
                    oldlen = len(self.inbuffer)
                    if self.history_pos > 1:
                        self.history_pos -= 1
                        if self.history_pos > 1:
                            self._fill_inbuffer(self.history[self.history_pos-2])
                        else:
                            self._reset_inbuffer()
                    else:
                        self._reset_inbuffer()
                    Console._erase_and_show(oldlen, self.inbuffer, self.cursor)
                    
                elif nxt == 'leftarrow':
                    if self.cursor > 0:
                        print(Console.seq['leftarrow'], end='')
                        self.cursor -= 1
                        
                elif nxt == 'rightarrow':
                    if self.cursor < len(self.inbuffer):
                        print(Console.seq['rightarrow'], end='')
                        self.cursor += 1
                        
                elif nxt == 'delete':
                    if self.cursor < len(self.inbuffer):
                        self._delete_and_show(self.cursor)                        
                        
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
            elif ch[0] == '\x7f' or ch[0] == '\x08':
                if self.cursor > 0:
                    current_cursor = self.cursor
                    self.cursor -= 1
                    self._delete_and_show(current_cursor)
                    
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
