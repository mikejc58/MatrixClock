# logger.py
import sys

def set_options(opts):
    global options
    options = opts
    
def set_time_keeper(tk):
    global time_keeper
    time_keeper = tk

def set_esp_mgr(espmgr):
    global esp_mgr
    esp_mgr = espmgr
    
class Logger:
    def __init__(self):
        self.AVAILABLE = True
    
    def print(self, text):
        self.message(text, do_print=True, add_time=False, traceback=False, exception_value=None, log=False)
        
    # Log messages to message_log.txt on the CIRCUITPY filesystem
    def message(self, outtext, do_print=True, add_time=True, traceback=False, exception_value=None, log=True):
        if log:
            if add_time:
                try:
                    outtext = "{} - {}".format(time_keeper.format_date_time(weekday=False), outtext)
                except NameError:
                    outtext = "                    - {}".format(outtext)
        if do_print:
            print(outtext)
            try:
                esp_mgr.send_to_socket(outtext)
            except NameError:
                pass
            if traceback:
                sys.print_exception(exception_value)
        if log:
            try:
                if self.AVAILABLE and options.get('logging'):
                    try:
                        try:
                            with open("/message_log.txt", "a") as wf:
                                wf.write(outtext + "\n")
                                if traceback:
                                    sys.print_exception(exception_value, wf)
                                wf.flush()
                        except OSError as e:
                            err_code = e.args[0]
                            self.AVAILABLE = False
                            options.replace('logging', False, show=False)
                            if err_code == 28:
                                self.message("Filesystem is full - logging disabled")
                            elif err_code == 30:
                                self.message("Filesystem is read-only - logging disabled")
                            else:
                                self.message("Logging got OSError ({}) - logging disabled".format(err_code))
                    except:
                        self.AVAILABLE = False
                        options.replace('logging', False, show=False)
                        self.message("Unexpected exception while logging - logging disabled")
            except NameError:
                pass

log = Logger()
