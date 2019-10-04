import re
import CommonExceptions as ces

"""
General utilities for parsing user input and other string expressions.
"""
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
