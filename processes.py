"""
Some helper functions to deal with processes.
"""

import os
import re

def list_matching(regex):
    """
    :param regex: A regular expression to math the process names agains
    :type regex: str or re.Pattern
    :returns: list(process names)
    """
    if isinstance(regex, str):
        regex = re.compile(regex)

    num_regex = re.compile('^[0-9]+$')
    name_regex = re.compile('^Name:\s*(.*)$')

    pns = []

    for l in os.listdir('/proc/'):
        if re.match(num_regex, l):
            with open('/proc/' + l + '/status') as sf:
                fl = sf.readline()

            m = re.match(name_regex, fl)
            if m:
                if re.match(regex, m.group(1)):
                    pns.append(m.group(1))

    return pns

def name_from_pid(pid):
    num_regex = re.compile('^[0-9]+$')
    name_regex = re.compile('^Name:\s*(.*)$')

    pns = []

    for l in os.listdir('/proc/'):
        if re.match(num_regex, l) and int(l) == pid:
            with open('/proc/' + l + '/status') as sf:
                fl = sf.readline()

            m = re.match(name_regex, fl)
            if m:
                return m.group(1)

    return None
