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
    BRIGHT_BLACK='\033[90m'
    BRIGHT_RED='\033[91m'
    BRIGHT_GREEN='\033[92m'
    BRIGHT_YELLOW='\033[93m'
    BRIGHT_BLUE='\033[94m'
    BRIGHT_MAGENTA='\033[95m'
    BRIGHT_CYAN='\033[96m'
    BRIGHT_WHITE='\033[97m'

    # Advanced colors
    ORANGE='\033[38;2;255;165;0m'

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


def print_status_box(text="", file=sys.stdout):
    file.write(Color.CYAN + "[      ] " + Color.NORMAL + text)
    file.flush()


def update_status_box(ok, file=sys.stdout):
    file.write('\r' + Color.CYAN + '[')
    
    if ok:
        print(Color.GREEN + '  OK  ' + Color.NORMAL, file=file)
    else:
        print(Color.RED + 'failed' + Color.NORMAL, file=file)


def print_finished_status_box(text="", ok=False, file=sys.stdout):
    """
    Like print_status_box + update_status_box in one call.
    """
    if ok:
        print(Color.CYAN + "[" + Color.GREEN + '  OK  ' + Color.CYAN + "] " +
            Color.NORMAL + text, file=file)
    else:
        print(Color.CYAN + "[" + Color.RED + 'failed' + Color.CYAN + "] " +
            Color.NORMAL + text, file=file)


def update_status_box_percent(v, ref, file=sys.stdout):
    p = int(float(v) / float(ref) * 100.)
    p = 0 if p < 0 else p
    p = 100 if p > 100 else p

    file.write('\r' + Color.CYAN + '[' +
            Color.MAGENTA + '{:4d}%'.format(p) + Color.NORMAL)

    file.flush()


def print_horizontal_bar(file=sys.stdout):
    c, r = shutil.get_terminal_size((80, 25))
    print(c * '-', file=file)
