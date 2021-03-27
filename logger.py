# logger.py
import sys

def set_options(opts):
    global options
    options = opts
    
def set_time_keeper(tk):
    global time_keeper
    time_keeper = tk

class Logger:
    def __init__(self):
        self.AVAILABLE = True
        
    # Log messages to message_log.txt on the CIRCUITPY filesystem
    def message(self, text, do_print=True, add_time=True, traceback=False, exception_value=None):
        outtext = "                    - {}".format(text)
        try:
            if add_time:
                outtext = "{} {} - {}".format(time_keeper.get_formatted_date(), time_keeper.get_formatted_time(), text)
        except NameError:
            pass
        if do_print:
            print(outtext)
            if traceback:
                sys.print_exception(exception_value)
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
