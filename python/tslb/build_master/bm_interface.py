"""
An interface between the build master and the client yamb interface.
"""
import queue
from tslb import Architecture
from tslb import CommonExceptions as ces


# Abstract interface
class BMInterface:
    """
    An abstract base class for the interface between build master and client
    yamb interface.
    """
    @property
    def identity(self):
        """
        A more- or less unique identity for this build master.

        :returns str:
        """
        raise NotImplementedError

    def get_remaining(self):
        """
        :returns list(tuple(str, VersionNumber)):
        """
        raise NotImplementedError

    def get_build_queue(self):
        """
        :returns list(tuple(str, VersionNumber)):
        """
        raise NotImplementedError

    def get_building_set(self):
        """
        :returns list(tuple(str, VersionNumber)):
        """
        raise NotImplementedError

    def get_nodes(self):
        """
        The list of idle nodes is in order of preference.

        :returns tuple(list(str), list(str)): tuple(idle, busy)
        """
        raise NotImplementedError

    def get_state(self):
        """
        :returns tuple(str, int, boolean, boolean): (state, arch, error, valve)
        """
        raise NotImplementedError

    def start(self, arch):
        """
        Start a build

        :param str/int arch:
        """
        raise NotImplementedError

    def stop(self):
        """
        Stop a build
        """
        raise NotImplementedError

    def open(self):
        """
        Open the 'package valve'
        """
        raise NotImplementedError

    def close(self):
        """
        Close the 'package valve'
        """
        raise NotImplementedError

    def subscribe(self, subscriber):
        """
        Subscribe for notifications. A notification includes the domain which
        changed. The following domains exist:

          * remaining
          * build_queue
          * nodes
          * state

        :param subscriber: A function with signature (BMInterface, domain:str)
        """
        raise NotImplementedError

    def unsubscribe(self, subscriber):
        raise NotImplementedError


# A mock build master controller
class MockController(BMInterface):
    def __init__(self, loop, identity):
        self._loop = loop
        self._identity = identity
        self._internal_state = 'off'
        self._error = False
        self._arch = Architecture.to_int('amd64')
        self._valve = False
        self._remaining = []
        self._build_queue = queue.LifoQueue()
        self._building_set = set()
        self._nodes = {}
        self._subscribers = []

    @property
    def identity(self):
        return self._identity

    def get_remaining(self):
        return list(self._remaining)

    def get_build_queue(self):
        return list(self._queue.queue)

    def get_building_set(self):
        return list(self._building_set)

    def get_nodes(self):
        idle = []
        busy = []

        for name, is_busy in self._nodes.items():
            if is_busy:
                idle.append(name)
            else:
                busy.append(name)

        idle.sort()
        return (idle, busy)

    def get_state(self):
        if self._building_set:
            state = 'building'
        else:
            state = self._internal_state

        return (state, self._arch, self._error, self._valve)

    def start(self, arch):
        if self._internal_state != 'off':
            raise ces.InvalidState(self._internal_state)

        self._arch = arch
        self._error = False
        self._valve = False
        self._remaining = ['pkg1', 'pkg2', 'pkg3', 'pkg4', 'pkg5', 'pkg6']

        while self._build_queue.qsize() > 0:
            self._build_queue.get()

        self._building_set.clear()
        self._nodes = {
            'node1': False,
            'node2': False
        }

        self._internal_state = 'computing'

    def stop(self):
        if self._building_set:
            raise ces.InvalidState('building')

        if self._internal_state != 'idle':
            raise ces.InvalidState(self._internal_state)

    def open(self):
        if self._internal_state not in ('idle', 'computing'):
            raise ces.InvalidState(self._internal_state)

        if self._error:
            raise ces.InvalidState('error condition present')

        if self._valve:
            raise ces.InvalidState('valve already open')

        self._valve = True

    def close(self):
        if self._internal_state not in ('idle', 'computing'):
            raise ces.InvalidState(self._internal_state)

        if self._error:
            raise ces.InvalidState('error condition present')

        if not self._valve:
            raise ces.InvalidState('valve already closed')

        self._valve = False

    def subscribe(self, subscriber):
        for subs in self._subscribers:
            if subs is subscriber:
                return

        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        for i, subs in enumerate(self._subscribers):
            if subs is subscriber:
                del self._subscribers[i]
                break


    def _notify_subscribers(self, domain):
        for subs in self._subscribers:
            subs(self, domain)
