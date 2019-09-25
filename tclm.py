"""
A singleton wrapper around tclmc from tclm_python_client.
"""

import threading
import tclm_python_client
import settings

# Connect
if 'TCLM' not in settings:
    raise Exception('TCLM section missing in TSLB config file.')

host = settings['TCLM'].get('host')
if not host:
    raise Exception('TCLM host not specified in TSLB config file.')

tclmc = tclm_python_client.create_tclmc(host)

# A thread local process
thlocal = threading.local()

def get_local_p():
    if not getattr(thlocal, 'p', None):
        thlocal.p = tclmc.register_process()

    return thlocal.p

# A wrapper around the locks to use the thread local process
class lock(object):
    def __init__(self, path):
        self.l = tclmc.define_lock(path)

    def create(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.create(p)

    def acquire_S(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.acquire_S(p)

    def acquire_Splus(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.acquire_Splus(p)

    def acquire_X(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.acquire_X(p)

    def release_S(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.release_S(p)

    def release_Splus(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.release_Splus(p)

    def release_X(self, p=None):
        if not p:
            p = get_local_p()

        return self.l.release_X(p)

    def get_path(self):
        return self.l.get_path()

# Wrap a tclmc's methods
def define_lock(path):
    return lock(path)

def register_process():
    return tclmc.register_process()

# Context managers for scoped locking
class lock_S(object):
    def __init__(self, lk):
        self.lk = lk

    def __enter__(self):
        self.lk.acquire_S()

    def __exit__(self, *args):
        self.lk.release_S()

class lock_Splus(object):
    def __init__(self, lk):
        self.lk = lk

    def __enter__(self):
        self.lk.acquire_Splus()

    def __exit__(self, *args):
        self.lk.release_Splus()

class lock_X(object):
    def __init__(self, lk):
        self.lk = lk

    def __enter__(self):
        self.lk.acquire_X()

    def __exit__(self, *args):
        self.lk.release_X()
