import sys
import shutil

class Color(object):
    BLACK='\033[30m'
    RED='\033[31m'
    GREEN='\033[32m'
    YELLOW='\033[33m'
    BLUE='\033[34m'
    MAGENTA='\033[35m'
    CYAN='\033[36m'
    WHITE ='\033[37m'
    NORMAL='\033[0m'

    def print_color(c, s, reset=True):
        return c + s + (Color.NORMAL if reset else "")

    def black(s, **kwargs):
        return Color.print_color(Color.BLACK, s, **kwargs)

    def red(s, **kwargs):
        return Color.print_color(Color.RED, s, **kwargs)

    def green(s, **kwargs):
        return Color.print_color(Color.GREEN, s, **kwargs)

    def yellow(s, **kwargs):
        return Color.print_color(Color.YELLOW, s, **kwargs)

    def blue(s, **kwargs):
        return Color.print_color(Color.BLUE, s, **kwargs)

    def magenta(s, **kwargs):
        return Color.print_color(Color.MAGENTA, s, **kwargs)

    def cyan(s, **kwargs):
        return Color.print_color(Color.CYAN, s, **kwargs)

    def white(s, **kwargs):
        return Color.print_color(Color.WHITE, s, **kwargs)


def print_status_box(text=""):
    sys.stdout.write(Color.CYAN + "[      ] " + Color.NORMAL + text)
    sys.stdout.flush()

def update_status_box(ok):
    sys.stdout.write('\r' + Color.CYAN + '[')
    
    if ok:
        print(Color.GREEN + '  OK  ' + Color.NORMAL)
    else:
        print(Color.RED + 'failed' + Color.NORMAL)

def update_status_box_percent(v, ref):
    p = int(float(v) / float(ref) * 100.)
    p = 0 if p < 0 else p
    p = 100 if p > 100 else p

    sys.stdout.write('\r' + Color.CYAN + '[' +
            Color.MAGENTA + '{:4d}%'.format(p) + Color.NORMAL)

    sys.stdout.flush()

def print_horizontal_bar():
    c, r = shutil.get_terminal_size((80, 25))
    print(c * '-')
