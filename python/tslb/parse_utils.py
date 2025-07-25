"""
General utilities for parsing user input and other string expressions.
"""
import re
from tslb import CommonExceptions as ces


def is_yes(e):
    if not e:
        return False

    e = e.lower().strip()
    return e == '1' or  e == 'true' or e == 'yes' or e == 'enabled'

def is_no(e):
    if not e:
        return False

    e = e.lower().strip()
    return e == '0' or  e == 'false' or e == 'no' or e == 'disabled'

def yes_or_no(text):
    """
    Throws an InvalidText exception if the text is neither yes nor no.
    """
    if is_yes(text):
        return True
    elif is_no(text):
        return False
    else:
        raise ces.InvalidText(text, 'Neither yes nor no')

def split_quotes(text):
    """
    Split a string on whitespaces respecting quotes.
    """
    if text:
        return re.findall(r'(?:[^\s"\']+|"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\')+', text)
    else:
        return None

def split_on_number_edge(text):
    """
    Split a string on number-letter and letter-number edges.

    i.e. '10gh434t' --> [ '10', 'gh', '434', 't' ]
    """
    if text is None:
        return None

    l = []

    buf = ''
    last_num = None

    for c in text:
        if last_num is None:
            buf += c
            last_num = c >= '0' and c <= '9'

        else:
            if last_num:
                if c >= '0' and c <= '9':
                    buf += c
                else:
                    last_num = False
                    l.append(buf)
                    buf=c
            else:
                if c < '0' or c > '9':
                    buf += c
                else:
                    last_num = True
                    l.append(buf)
                    buf=c

    l.append(buf)

    return l


def stringify_escapes(s):
    """
    Convert escape sequences to string representation, i.e. '\n' -> '\\n'.

    :param str s: Input string
    :returns str: Output string with escape sequences replaced.
    """
    output = ""

    for c in s:
        if c == '\n':
            output += '\\n'
        elif c == '\r':
            output += '\\r'
        elif c == '\033':
            output += '\\033'
        else:
            output += c

    return output


def query_user_input(prompt, options):
    """
    Query user input from stdin using `input`.

    :param str options: e.g. yNa -> y, n, or a with n being the default
    """
    default = None
    for o in options:
        if o.isupper():
            default = o.lower()

    loptions = options.lower()
    while True:
        r = input("%s [%s]: " % (prompt, '/'.join(options))).lower()
        if not r and default:
            return default
        elif len(r) == 1 and r in loptions:
            return r
