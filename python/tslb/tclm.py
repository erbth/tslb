"""
A singleton wrapper around tclmc from tclm_python_client.
"""

import threading
import tclm_python_client
from tslb import settings
from tslb import parse_utils

# Connect
if 'TCLM' not in settings:
    raise Exception('TCLM section missing in TSLB config file.')

host = settings['TCLM'].get('host')
if not host:
    raise Exception('TCLM host not specified in TSLB config file.')

trace_enabled = parse_utils.is_yes(settings['TCLM'].get('trace'))

tclmc = None

def ensure_connection():
    global tclmc

    if tclmc is None:
        tclmc = tclm_python_client.create_tclmc(host)

# A thread local process
thlocal = threading.local()

def get_local_p():
    if not getattr(thlocal, 'p', None):
        ensure_connection()
        thlocal.p = tclmc.register_process()

    return thlocal.p


class lock(object):
    """
    A wrapper around a TCLM lock that uses the thread local process TCLM
    process.

    :param path: The lock's path.
    """
    def __init__(self, path):
        ensure_connection()
        self.l = tclmc.define_lock(path)

    def create(self, acquire_X, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.create(%s, %s)" % (self.l.get_path(), p.get_id(), acquire_X))

        return self.l.create(p, acquire_X)

    def acquire_S(self, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.acquire_S(%s)" % (self.l.get_path(), p.get_id()))

        return self.l.acquire_S(p)

    def acquire_Splus(self, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.acquire_Splus(%s)" % (self.l.get_path(), p.get_id()))

        return self.l.acquire_Splus(p)

    def acquire_X(self, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.acquire_X(%s)" % (self.l.get_path(), p.get_id()))

        return self.l.acquire_X(p)

    def release_S(self, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.release_S(%s)" % (self.l.get_path(), p.get_id()))

        return self.l.release_S(p)

    def release_Splus(self, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.release_Splus(%s)" % (self.l.get_path(), p.get_id()))

        return self.l.release_Splus(p)

    def release_X(self, p=None):
        if not p:
            p = get_local_p()

        if trace_enabled:
            print ("TCLM: `%s'.release_X(%s)" % (self.l.get_path(), p.get_id()))

        return self.l.release_X(p)

    def get_path(self):
        return self.l.get_path()


    def __repr__(self):
        return ('lock(\"%s\")' % self.get_path())


# Wrap a tclmc's methods
def define_lock(path):
    return lock(path)

def register_process():
    ensure_connection()
    return tclmc.register_process()

# Context managers for scoped locking
class lock_S(object):
    """
    Context manager that holds the specified lock in S mode.
    """
    def __init__(self, lk):
        self.lk = lk

    def __enter__(self):
        self.lk.acquire_S()

    def __exit__(self, *args):
        self.lk.release_S()


class lock_Splus(object):
    """
    Context manager that holds the specified lock in S+ mode.
    """
    def __init__(self, lk):
        self.lk = lk

    def __enter__(self):
        self.lk.acquire_Splus()

    def __exit__(self, *args):
        self.lk.release_Splus()


class lock_X(object):
    """
    Context manager that holds the specified lock in X mode.
    """
    def __init__(self, lk):
        self.lk = lk

    def __enter__(self):
        self.lk.acquire_X()

    def __exit__(self, *args):
        self.lk.release_X()
