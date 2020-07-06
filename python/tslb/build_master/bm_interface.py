"""
An interface between the build master and the client yamb interface.
"""
import queue
import random
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb.VersionNumber import VersionNumber


# Abstract interface
class BMInterface:
    """
    An abstract base class for the interface between build master and client
    yamb interface.
    """
    DOMAIN_STATE = 0
    DOMAIN_REMAINING = 1
    DOMAIN_BUILD_QUEUE = 2
    DOMAIN_BUILDING_SET = 3
    DOMAIN_NODES = 4
    DOMAIN_ALL = 100

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
        :raises ces.InvalidState:
        """
        raise NotImplementedError

    def stop(self):
        """
        Stop a build

        :raises ces.InvalidState:
        """
        raise NotImplementedError

    def open(self):
        """
        Open the 'package valve'

        :raises ces.InvalidState:
        """
        raise NotImplementedError

    def close(self):
        """
        Close the 'package valve'

        :raises ces.InvalidState:
        """
        raise NotImplementedError

    def subscribe(self, subscriber):
        """
        Subscribe for notifications. A notification includes the domain which
        changed. The following domains exist:

          * remaining
          * build_queue
          * building_set
          * nodes
          * state
          * all,

        have a look at the constants defined above.

        :param subscriber: A function with signature (BMInterface, domain:str)
        """
        raise NotImplementedError

    def unsubscribe(self, subscriber):
        raise NotImplementedError

    def register_log_handler(self, handler):
        """
        Register a log handler.

        :param handler: A function with signature (msg:str, flush=False) that
            does not print newlines.
        """
        raise NotImplementedError

    def deregister_log_handler(self, handler):
        raise NotImplementedError


# A mock build master controller
class MockController(BMInterface):
    def __init__(self, loop, yamb_node, identity):
        self._loop = loop
        self._identity = identity
        self._internal_state = 'off'
        self._error = False
        self._arch = Architecture.to_int('amd64')
        self._valve = False
        self._remaining = []
        self._build_queue = queue.Queue()
        self._building_set = set()
        self._nodes = {}
        self._subscribers = []

        self._log_handlers = []

    @property
    def identity(self):
        return self._identity

    def get_remaining(self):
        return list(self._remaining)

    def get_build_queue(self):
        return list(self._build_queue.queue)

    def get_building_set(self):
        return list(self._building_set)

    def get_nodes(self):
        idle = []
        busy = []

        for name, is_busy in self._nodes.items():
            if is_busy:
                busy.append(name)
            else:
                idle.append(name)

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
        self._remaining = [
            ('pkg1', VersionNumber('1.0')),
            ('pkg2', VersionNumber('1.2')),
            ('pkg3', VersionNumber('1.4')),
            ('pkg4', VersionNumber('2.0')),
            ('pkg5', VersionNumber('1')),
            ('pkg6', VersionNumber('1.0.1')),
            ('pkg7', VersionNumber('1.0')),
            ('pkg8', VersionNumber('1.2')),
            ('pkg9', VersionNumber('1.4')),
            ('pkg10', VersionNumber('2.0')),
            ('pkg11', VersionNumber('1')),
            ('pkg12', VersionNumber('1.0.1'))
        ]

        while self._build_queue.qsize() > 0:
            self._build_queue.get()

        self._building_set.clear()
        self._nodes = {
            'node1': False,
            'node2': False
        }

        self._internal_state = 'computing'

        self._notify_subscribers(self.DOMAIN_ALL)

        # Start computing
        self._loop.call_later(1, self._compute)


    def stop(self):
        if self._building_set:
            raise ces.InvalidState('building')

        if self._internal_state != 'idle':
            raise ces.InvalidState(self._internal_state)

        self._error = False
        self._valve = False
        self._remaining = []

        while self._build_queue.qsize() > 0:
            self._build_queue.get()

        self._building_set.clear()
        self._nodes = {}

        self._internal_state = 'off'

        self._notify_subscribers(self.DOMAIN_ALL)


    def open(self):
        if self._internal_state not in ('idle', 'computing'):
            raise ces.InvalidState(self._internal_state)

        if self._error:
            raise ces.InvalidState('error condition present')

        if self._valve:
            raise ces.InvalidState('valve already open')

        self._valve = True

        self._notify_subscribers(self.DOMAIN_STATE)

        self._schedule()


    def close(self):
        if self._internal_state not in ('idle', 'computing'):
            raise ces.InvalidState(self._internal_state)

        if self._error:
            raise ces.InvalidState('error condition present')

        if not self._valve:
            raise ces.InvalidState('valve already closed')

        self._valve = False

        self._notify_subscribers(self.DOMAIN_STATE)


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

    def register_log_handler(self, handler):
        for h in self._log_handlers:
            if h is handler:
                return

        self._log_handlers.append(handler)

    def deregister_log_handler(self, handler):
        for i, h in enumerate(self._log_handlers):
            if h is handler:
                del self._log_handlers[i]
                break


    def _notify_subscribers(self, domain):
        for subs in self._subscribers:
            subs(self, domain)

    def _log(self, msg, flush=False):
        for h in self._log_handlers:
            h(msg, flush)


    # Emulating a build master
    def _compute(self):
        pkg = self._remaining[0]

        self._log("Adding `%s:%s' to the build queue ...\n" % pkg)
        self._log("\033[48;2;190;36;6m                     \033[0m\n")

        self._build_queue.put(pkg)
        del self._remaining[0]

        self._notify_subscribers(self.DOMAIN_REMAINING)
        self._notify_subscribers(self.DOMAIN_BUILD_QUEUE)
        
        if not self._remaining:
            self._internal_state = "idle"
            self._notify_subscribers(self.DOMAIN_STATE)

        else:
            self._loop.call_later(1, self._compute)

        self._schedule()


    def _schedule(self):
        if self._valve:
            # Find free nodes
            free_nodes = []
            for name, busy in self._nodes.items():
                if not busy:
                    free_nodes.append(name)

            while self._build_queue.qsize() > 0 and free_nodes:
                pkg = self._build_queue.get()
                node = free_nodes[-1]
                free_nodes.pop()

                self._bind(pkg, node)

        self._notify_subscribers(self.DOMAIN_BUILD_QUEUE)
        self._notify_subscribers(self.DOMAIN_BUILDING_SET)
        self._notify_subscribers(self.DOMAIN_NODES)
        self._notify_subscribers(self.DOMAIN_STATE)


    def _bind(self, pkg, node):
        self._nodes[node] = True
        self._building_set.add(pkg)

        # Start build
        self._loop.call_later(2 + random.random() * 2, self._complete_build, pkg, node)

    def _complete_build(self, pkg, node):
        self._nodes[node] = False
        self._building_set.remove(pkg)

        # if pkg[0] == 'pkg7':
        #     self._fail()

        # else:
        #     self._schedule()

        self._schedule()


    def _fail(self):
        self._error = True
        self._valve = False

        self._schedule()
