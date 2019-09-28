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
